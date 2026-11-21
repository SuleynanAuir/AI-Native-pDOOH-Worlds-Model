"""Resumable per-screen OASIS coverage; only completed, scored scenes are published."""
import os,time,threading
from pathlib import Path
from . import store
from .world import read_json,write_json
from .campaign import job_dir,scene_people,analyze_people,materialize_scene
from .investment import campaign_evidence,summarize
_lock=threading.Lock()


def path(root,pid,cid):
    job_dir(Path(root)/'campaign_experiments',cid)
    return store.directory(root,pid)/('coverage-'+cid)


def status(root,pid,cid):
    p=path(root,pid,cid)/'state.json'
    if not p.exists():return dict(status='not_started',done=0,total=0,items={})
    s=read_json(p)
    if s['status']=='running':
        try:os.kill(s['pid'],0)
        except ProcessLookupError:s['status']='interrupted'
    return s


def supplement(root,pid,cid,evidence,threshold=60):
    if not cid:return
    p=path(root,pid,cid)
    if not (p/'state.json').exists():return
    s=read_json(p/'state.json')
    if s.get('fingerprint')!=evidence['fingerprint']:return
    for item in s['items'].values():
        if item.get('status')=='completed':
            for sid,row in summarize(read_json(p/'scenes'/item['scene_id']/'base.json'),threshold).items():
                if sid not in evidence['screens']:evidence['screens'][sid]=row


def start(app,pid,cid):
    root=app.config['UPLOAD_FOLDER'];p=path(root,pid,cid);evidence=campaign_evidence(root,cid)
    with _lock:
        old=status(root,pid,cid)
        if old['status']=='running':return old
        if old.get('fingerprint') not in (None,evidence['fingerprint']):raise ValueError('广告证据已改变，请创建新的广告实验')
        with store.locked(root,pid) as (_,project): ids={f['screen_id'] for f in project['frames'] if f['screen_id']}
        ids-=set(evidence['screens']);p.mkdir(exist_ok=True)
        s=dict(status='running',pid=os.getpid(),total=len(ids),done=0,items=old.get('items',{}),fingerprint=evidence['fingerprint'],threshold=60,message='准备逐屏地图与OASIS任务')
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
            research=read_json(job_dir(Path(root)/'campaign_experiments',cid)/'research.json')
            for frame in inventory['frames']:
                sid=frame['screen_id']
                if sid not in ids:continue
                item=s['items'].setdefault(sid,{})
                if item.get('status')=='completed':continue
                try:
                    item.update(status='running',error=None);s['message']='查证地点：'+sid;save()
                    if not item.get('context'):item['context']=post('locate-frame',dict(inventory_id=inventory['id'],frame_key=frame['key'],radius_m=400));save()
                    if not item.get('template'):item['template']=post('local-audiences',dict(locality=item['context']['locality'],group_count=12));save()
                    if not item.get('run_id'):
                        run=post('runs',dict(agent_count=100,total_population=30000,seed=42,day_cycle={'days':1},locality=item['context']['locality'],template_id=item['template']['id']))
                        item['run_id']=run['id'];save()
                    s['message']='OASIS全天模拟：'+sid;save()
                    while True:
                        state=read_json(Path(root)/'worlds'/item['run_id']/'state.json')
                        item['round']=state.get('current_round',0);save()
                        if state['status']=='completed':break
                        if state['status'] in ('failed','stopped'):
                            item.pop('run_id',None);raise ValueError('OASIS运行失败，可重试')
                        time.sleep(3)
                    meta=post('comparison-scenes/import',{'run_id':item['run_id']});scene_id=meta['id']
                    directory=Path(root)/'scene_library'/scene_id;base=read_json(directory/'base.json');base['_path']=directory
                    people,locality,schedule,seed=scene_people(base,Path(root)/'worlds'/item['run_id'])
                    s['message']='生成该屏幕100个代表的广告态度：'+sid;save()
                    attitude=analyze_people(people,base['groups'],locality,research,app.config)
                    materialize_scene(p/'scenes'/scene_id,base,people,locality,schedule,seed,research,attitude,1800)
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
