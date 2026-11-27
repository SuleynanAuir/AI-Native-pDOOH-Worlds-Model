"""Resumable per-screen OASIS coverage; only completed, scored scenes are published."""
import os,time,threading,hashlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from . import store
from .world import read_json,write_json
from .campaign import job_dir,scene_people,analyze_people,materialize_scene,scene_flow
from .investment import campaign_evidence,summarize
from .process_health import alive
_lock=threading.Lock()
_active=set()


def path(root,pid,cid):
    job_dir(Path(root)/'campaign_experiments',cid)
    return store.directory(root,pid)/('coverage-'+cid)



def input_path(folder,sid):
    directory=folder/'inputs';directory.mkdir(exist_ok=True)
    return directory/(hashlib.sha256(sid.encode()).hexdigest()+'.json')


def externalize_inputs(folder,items):
    """Archive bulky immutable inputs before removing them from hot progress state."""
    for sid,item in items.items():
        fields={key:item[key] for key in ('context','template') if key in item}
        if not fields:continue
        target=input_path(folder,sid)
        previous=read_json(target) if target.exists() else {}
        write_json(target,{**previous,**fields})
        for key in fields:item.pop(key)
        item['inputs_saved']=True

def status(root,pid,cid):
    p=path(root,pid,cid)/'state.json'
    if not p.exists():return dict(status='not_started',done=0,total=0,items={})
    s=read_json(p)
    if s['status']=='running':
        if not alive(s.get('pid')):s['status']='interrupted'
        for item in s.get('items',{}).values():
            if item.get('status')=='running' and item.get('run_id'):
                rp=Path(root)/'worlds'/item['run_id']
                if (rp/'state.json').exists() and read_json(rp/'progress.json' if (rp/'progress.json').exists() else rp/'state.json')['status'] not in ('completed','failed','stopped'):
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
        if (str(p) in _active) or old['status']=='running':return old
        if old.get('fingerprint') not in (None,evidence['fingerprint']):raise ValueError('广告证据已改变，请创建新的广告实验')
        with store.locked(root,pid) as (_,project):
            from .planning import clean
            frames=clean(project,{})
            ids={f['screen_id'] for f in frames if f['screen_id']}
        ids=(ids-set(evidence['screens'])) | (ids & {sid for sid,item in old.get('items',{}).items() if item.get('status')=='completed'});p.mkdir(exist_ok=True)
        items=old.get('items',{})
        for item in items.values():
            if item.get('status')=='failed':item['status']='pending'
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
        externalize_inputs(p,items)
        s=dict(simulation_mode='policy_simulation_v1' if os.environ.get('PDOOH_POLICY_SIMULATION','false').lower()=='true' else 'batched_interviews_v2',status='running',pid=os.getpid(),total=len(ids),done=sum(i.get('status')=='completed' for i in items.values()),items=items,fingerprint=evidence['fingerprint'],threshold=60,message='准备逐屏地图与OASIS任务')
        write_json(p/'state.json',s)
        _active.add(str(p))
    def worker():
        state_lock=threading.RLock()
        consecutive_failures=[0]
        analysis_pool=ThreadPoolExecutor(max_workers=3,thread_name_prefix="screen-attitude")
        def save():
            with state_lock:
                s['done']=sum(i.get('status')=='completed' for i in s['items'].values());write_json(p/'state.json',s)
        def measured(item,stage,fn,*args,**kwargs):
            began=time.perf_counter()
            try:return fn(*args,**kwargs)
            finally:
                with state_lock:item.setdefault('timings',{})[stage]=round(time.perf_counter()-began,3)
                save()
        def analyze_cached(sid,item,scene):
            folder=p/'attitudes';folder.mkdir(exist_ok=True)
            cache=folder/(hashlib.sha256(sid.encode()).hexdigest()+'.json')
            if cache.exists():return read_json(cache)
            value=measured(item,'advertising',analyze_people,scene['agents'],scene['groups'],scene.get('locality',{}),research,app.config)
            write_json(cache,value)
            return value
        def post(url,data):
            while True:
                r=app.test_client().post('/api/world/'+url,json=data)
                if url!='runs' or r.status_code!=429:break
                time.sleep(3)
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
            pending=list({f['screen_id']:f for f in inventory['frames'] if f['screen_id'] in ids}.values())
            for frame in pending:s['items'].setdefault(frame['screen_id'],{})
            workers=max(1,min(3,int(app.config.get('COVERAGE_WORKERS',3))))
            s['workers']=workers
            save()
            def process_frame_once(frame):
                sid=frame['screen_id'];item=s['items'][sid]
                if item.get('status')=='completed':return
                with state_lock:
                    if consecutive_failures[0]>=3:return
                try:
                    inputs_file=input_path(p,sid)
                    inputs=read_json(inputs_file) if inputs_file.exists() else {}
                    item.setdefault('started_at',time.time())
                    item['attempt_started_at']=time.time()
                    if item.get('run_id'):
                        rp=Path(root)/'worlds'/item['run_id']
                        process=read_json(rp/'process.json') if (rp/'process.json').exists() else {}
                        if read_json(rp/'state.json')['status']!='completed' and not alive(process.get('pid')):item.pop('run_id',None)
                    item.update(status='running',error=None);s['message']='查证地点：'+sid;save()
                    if not item.get('run_id') and not inputs.get('context'):inputs['context']=measured(item,'location',post,'locate-frame',dict(inventory_id=inventory['id'],frame_key=frame['key'],radius_m=400,defer_inference=True));write_json(inputs_file,inputs);save()
                    if not item.get('run_id') and not inputs.get('template'):inputs['template']=measured(item,'audiences',post,'local-audiences',dict(locality=inputs['context']['locality'],group_count=12));write_json(inputs_file,inputs);save()
                    if item.get('run_id'):
                        rp=Path(root)/'worlds'/item['run_id']
                        process=read_json(rp/'process.json') if (rp/'process.json').exists() else {}
                        if read_json(rp/'state.json')['status']!='completed' and not alive(process.get('pid')):item.pop('run_id',None)
                    if not item.get('run_id'):
                        run=measured(item,'scene_setup',post,'runs',dict(agent_count=100,total_population=30000,seed=42,day_cycle={'days':1},locality=inputs['context']['locality'],template_id=inputs['template']['id']))
                        item['run_id']=run['id'];save()
                    initial=read_json(Path(root)/'worlds'/item['run_id']/'state.json')
                    attitude_future=analysis_pool.submit(analyze_cached,sid,item,initial['scene'])
                    simulation_began=time.perf_counter()
                    s['message']='全天行为推演：'+sid;save()
                    while True:
                        run_path=Path(root)/'worlds'/item['run_id']
                        state=read_json(run_path/'progress.json' if (run_path/'progress.json').exists() else run_path/'state.json')
                        item['round']=state.get('current_round',0);save()
                        if state['status']=='completed':
                            state=read_json(run_path/'state.json')
                            break
                        process=read_json(Path(root)/'worlds'/item['run_id']/'process.json')
                        if not alive(process.get('pid')):
                            final_state=read_json(run_path/'state.json')
                            if final_state.get('status')=='completed':state=final_state;break
                            item.pop('run_id',None);raise ValueError(final_state.get('message') if final_state.get('status')=='failed' else '模拟子进程退出，已保留完成屏幕，可重试')
                        if state['status'] in ('failed','stopped'):
                            item.pop('run_id',None);raise ValueError('OASIS运行失败，可重试')
                        time.sleep(3)
                    item.setdefault('timings',{})['simulation_wait']=round(time.perf_counter()-simulation_began,3)
                    if fresh:
                        from .simulation_workflow import full_day
                        if not full_day(state) or state.get('started_at',0)<batch['created_at']:raise ValueError('本轮必须从00:00完成全部24小时，不能采用历史或不完整运行')
                    meta=measured(item,'pedestrian_replay',post,'comparison-scenes/import',{'run_id':item['run_id'],'pedestrians_only':True});scene_id=meta['id']
                    directory=Path(root)/'scene_library'/scene_id;base=read_json(directory/'base.json');base['_path']=directory
                    people,locality,schedule,seed=scene_people(base,Path(root)/'worlds'/item['run_id'])
                    s['message']='生成该屏幕100个代表的广告态度：'+sid;save()
                    attitude=attitude_future.result()
                    flow,estimate=scene_flow(campaign_spec,base)
                    measured(item,'final_replay',materialize_scene,p/'scenes'/scene_id,base,people,locality,schedule,seed,research,attitude,flow,estimate,max_vehicle_samples=300)
                    item.update(status='completed',decision_method=state.get('decision_method'),scene_id=scene_id,completed_at=time.time(),total_seconds=round(time.time()-item['attempt_started_at'],3),lifecycle_seconds=round(time.time()-item['started_at'],3))
                    with state_lock:consecutive_failures[0]=0
                    save()
                except Exception as exc:
                    with state_lock:consecutive_failures[0]+=1
                    item.update(status='failed',error=str(exc)[:250] if isinstance(exc,ValueError) else '外部服务或运行失败，可重试');save()
                    # Stop a failing provider from being called for the entire inventory.
                    return
            def process_frame(frame):
                item=s['items'][frame['screen_id']]
                for attempt in range(2):
                    process_frame_once(frame)
                    if item.get('status')!='failed':return
                    if attempt==0:
                        with state_lock:item.update(status='pending',retry_count=item.get('retry_count',0)+1)
                        save();time.sleep(1)
            with ThreadPoolExecutor(max_workers=workers,thread_name_prefix='screen-coverage') as executor:
                list(executor.map(process_frame,pending))
            s['status']='completed' if s['done']==s['total'] else 'interrupted';s['message']='全部屏幕处理完成，可以生成报告' if s['status']=='completed' else ('连续任务失败，已暂停；已完成结果保留，可继续重试' if consecutive_failures[0]>=3 else '部分屏幕未完成，已保留结果，可重试失败屏幕')
        except Exception as exc:s.update(status='failed',message=str(exc)[:200] if isinstance(exc,ValueError) else '任务失败，可重试')
        finally:
            analysis_pool.shutdown(wait=False)
            try:save()
            finally:
                with _lock:_active.discard(str(p))
    threading.Thread(target=worker,daemon=True).start()
    return s
