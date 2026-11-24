"""Resumable per-screen OASIS coverage; only completed, scored scenes are published."""
import os,time,threading
from pathlib import Path
from . import store
from .world import read_json,write_json
from .campaign import job_dir,scene_people,analyze_people,materialize_scene,scene_flow
from .investment import campaign_evidence,summarize
from .process_health import alive
_lock=threading.Lock()


def path(root,pid,cid):
    job_dir(Path(root)/'campaign_experiments',cid)
    return store.directory(root,pid)/('coverage-'+cid)


def status(root,pid,cid):
    p=path(root,pid,cid)/'state.json'
    if not p.exists():return dict(status='not_started',done=0,total=0,items={})
    s=read_json(p)
    if s['status']=='running':
        if not alive(s.get('pid')):s['status']='interrupted'
        for item in s.get('items',{}).values():
            if item.get('status')=='running' and item.get('run_id'):
                rp=Path(root)/'worlds'/item['run_id']
                if (rp/'state.json').exists() and read_json(rp/'state.json')['status'] not in ('completed','failed','stopped'):
                    process=read_json(rp/'process.json') if (rp/'process.json').exists() else {}
                    if not alive(process.get('pid')):s.update(status='interrupted',message='OASIS子进程已退出，可从已完成屏幕继续')
    return s


def supplement(root,pid,cid,evidence,threshold=60):
    if not cid:return
    p=path(root,pid,cid)
    if not (p/'state.json').exists():return
    s=read_json(p/'state.json')
    if s.get('fingerprint')!=evidence['fingerprint']:return
    for item in s['items'].values():
        if item.get('status')=='completed':
            try:base=read_json(p/'scenes'/item['scene_id']/'base.json')
            except (OSError,ValueError):
                evidence.setdefault('unreadable_results',[]).append(item['scene_id']);continue
            if base.get('meta',{}).get('source_type')=='preview':continue
            for sid,row in summarize(base,threshold).items():
                if sid not in evidence['screens']:evidence['screens'][sid]=row


def start(app,pid,cid):
    root=app.config['UPLOAD_FOLDER'];p=path(root,pid,cid)
    from .investment_evidence import resolve
    with store.locked(root,pid) as (_,project):
        spec=read_json(job_dir(Path(root)/'campaign_experiments',cid)/'state.json')['spec']
        fresh=spec.get('fresh_day',False)
        batch=project.get('simulation_batch',{})
        if fresh:
            from .simulation_workflow import signature
            if batch.get('id')!=cid or batch.get('signature')!=signature(project):raise ValueError('本轮设置已变化，请重新开始全天模拟')
            evidence=dict(screens={},fingerprint=batch['signature'])
        else:evidence=resolve(root,project,cid)
        setup=project.get('ad_setup',{})
    with _lock:
        old=status(root,pid,cid)
        if old['status']=='running':return old
        if old.get('fingerprint') not in (None,evidence['fingerprint']):raise ValueError('广告证据已改变，请创建新的广告实验')
        with store.locked(root,pid) as (_,project):
            from .planning import clean
            frames=clean(project,{})
            ids={f['screen_id'] for f in frames if f['screen_id']}
        ids=(ids-set(evidence['screens'])) | (ids & {sid for sid,item in old.get('items',{}).items() if item.get('status')=='completed'});p.mkdir(exist_ok=True)
        items=old.get('items',{})
        from .geolocation import distance_m
        frame_by_id={f['screen_id']:f for f in frames}
        for meta_path in ([] if fresh else sorted((Path(root)/'scene_library').glob('*/meta.json'))):
            try:
                meta=read_json(meta_path);sid=meta.get('screen_id');f=frame_by_id.get(sid);coordinate=meta.get('coordinate')
                if sid not in ids or not f or not coordinate or meta.get('source_type')!='oasis' or meta.get('rounds',0)<24:continue
                if f['lat'] is None or f['lon'] is None or distance_m(f['lat'],f['lon'],coordinate['lat'],coordinate['lon'])>30:continue
                run=read_json(Path(root)/'worlds'/meta['run_id']/'state.json')
                if run['status']=='completed' and not items.get(sid,{}).get('run_id'):items.setdefault(sid,{}).update(run_id=meta['run_id'],reused_oasis=True)
            except (OSError,ValueError,KeyError):continue
        s=dict(status='running',pid=os.getpid(),total=len(ids),done=0,items=items,fingerprint=evidence['fingerprint'],threshold=60,message='准备逐屏地图与OASIS任务')
        write_json(p/'state.json',s)
    def worker():
        client=app.test_client()
        def save():
            s['done']=sum(i.get('status')=='completed' for i in s['items'].values());write_json(p/'state.json',s)
        def post(url,data):
            r=client.post('/api/world/'+url,json=data)
            if r.status_code>=400:raise ValueError((r.json or {}).get('error','请求失败'))
            return r.json['data']
        try:
            inventory=post('geo-inventory',{'project_id':pid})
            campaign_path=job_dir(Path(root)/'campaign_experiments',cid)
            if not (campaign_path/'research.json').exists():
                from .campaign_research import research as research_ad
                write_json(campaign_path/'research.json',research_ad(spec['campaign'],[],app.config))
            research=read_json(campaign_path/'research.json')
            campaign_spec={**read_json(campaign_path/'state.json')['spec'],'traffic_estimates':setup.get('traffic_estimates',{}),'traffic_manual':setup.get('vehicles_per_hour')}
            for frame in inventory['frames']:
                sid=frame['screen_id']
                if sid not in ids:continue
                item=s['items'].setdefault(sid,{})
                if item.get('status')=='completed':continue
                try:
                    if item.get('run_id'):
                        rp=Path(root)/'worlds'/item['run_id']
                        process=read_json(rp/'process.json') if (rp/'process.json').exists() else {}
                        if read_json(rp/'state.json')['status']!='completed' and not alive(process.get('pid')):item.pop('run_id',None)
                    item.update(status='running',error=None);s['message']='查证地点：'+sid;save()
                    if not item.get('run_id') and not item.get('context'):item['context']=post('locate-frame',dict(inventory_id=inventory['id'],frame_key=frame['key'],radius_m=400));save()
                    if not item.get('run_id') and not item.get('template'):item['template']=post('local-audiences',dict(locality=item['context']['locality'],group_count=12));save()
                    if item.get('run_id'):
                        rp=Path(root)/'worlds'/item['run_id']
                        process=read_json(rp/'process.json') if (rp/'process.json').exists() else {}
                        if read_json(rp/'state.json')['status']!='completed' and not alive(process.get('pid')):item.pop('run_id',None)
                    if not item.get('run_id'):
                        run=post('runs',dict(agent_count=100,total_population=30000,seed=42,day_cycle={'days':1},locality=item['context']['locality'],template_id=item['template']['id']))
                        item['run_id']=run['id'];save()
                    s['message']='OASIS全天模拟：'+sid;save()
                    while True:
                        state=read_json(Path(root)/'worlds'/item['run_id']/'state.json')
                        item['round']=state.get('current_round',0);save()
                        if state['status']=='completed':break
                        process=read_json(Path(root)/'worlds'/item['run_id']/'process.json')
                        if not alive(process.get('pid')):item.pop('run_id',None);raise ValueError('OASIS子进程退出，已保留完成屏幕，可重试')
                        if state['status'] in ('failed','stopped'):
                            item.pop('run_id',None);raise ValueError('OASIS运行失败，可重试')
                        time.sleep(3)
                    if fresh:
                        from .simulation_workflow import full_day
                        if not full_day(state) or state.get('started_at',0)<batch['created_at']:raise ValueError('本轮必须从00:00完成全部24小时，不能采用历史或不完整运行')
                    meta=post('comparison-scenes/import',{'run_id':item['run_id']});scene_id=meta['id']
                    directory=Path(root)/'scene_library'/scene_id;base=read_json(directory/'base.json');base['_path']=directory
                    people,locality,schedule,seed=scene_people(base,Path(root)/'worlds'/item['run_id'])
                    s['message']='生成该屏幕100个代表的广告态度：'+sid;save()
                    attitude=analyze_people(people,base['groups'],locality,research,app.config)
                    flow,estimate=scene_flow(campaign_spec,base)
                    materialize_scene(p/'scenes'/scene_id,base,people,locality,schedule,seed,research,attitude,flow,estimate)
                    item.update(status='completed',scene_id=scene_id);save()
                except Exception as exc:
                    item.update(status='failed',error=str(exc)[:250] if isinstance(exc,ValueError) else '外部服务或运行失败，可重试');save()
                    # Stop a failing provider from being called for the entire inventory.
                    if sum(i.get('status')=='failed' for i in s['items'].values())>=3:break
            s['status']='completed' if s['done']==s['total'] else 'interrupted';s['message']='本批完成；重新计算投资方案以应用已完成屏幕'
        except Exception as exc:s.update(status='failed',message=str(exc)[:200] if isinstance(exc,ValueError) else '任务失败，可重试')
        finally:save()
    threading.Thread(target=worker,daemon=True).start()
    return s
