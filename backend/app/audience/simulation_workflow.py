"""Fresh, project-bound midnight-to-midnight runs are required for final reports."""
import hashlib,json,time,uuid
from functools import lru_cache
from pathlib import Path
from . import store
from .world import read_json,write_json


def signature(project):
    setup=project.get('ad_setup',{})
    payload=dict(frames=project['frames'],campaign=setup.get('campaign'),creative=setup.get('creative'),
                 traffic=setup.get('traffic_estimates'),manual=setup.get('vehicles_per_hour'),documents=project.get('documents'),day_hours=list(range(24)),version=1)
    return hashlib.sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def full_day(run):
    scene=run.get('scene',{});schedule=scene.get('schedule',[])
    snapshots=run.get('snapshots',[])
    return (run.get('status')=='completed' and str(run.get('engine','')).startswith('OASIS') and run.get('current_round')==24
        and scene.get('rounds')==24 and len(schedule)==24 and [s.get('hour') for s in schedule]==list(range(24))
        and [s.get('round') for s in schedule]==list(range(1,25))
        and {s.get('round') for s in snapshots if s.get('round',0)>0}==set(range(1,25)))


def begin(root,pid):
    with store.locked(root,pid) as (path,project):
        if not project.get('ad_setup',{}).get('campaign'):raise ValueError('请先保存第二步广告设置')
        digest=signature(project);old=project.get('simulation_batch')
        if old and old['signature']==digest:return old
        cid=uuid.uuid4().hex;directory=Path(root)/'campaign_experiments'/cid;directory.mkdir(parents=True)
        setup=project['ad_setup'];campaign=dict(setup['campaign'])
        if setup.get('creative'):
            asset=setup['creative'];campaign['creative_asset']={k:asset.get(k) for k in ('id','name','url')}
            if asset.get('description'):campaign['creative_observation']=asset['description']
        batch=dict(id=cid,signature=digest,created_at=time.time(),screen_ids=sorted({f['screen_id'] for f in project['frames'] if f.get('screen_id')}))
        spec=dict(scene_ids=[],campaign=campaign,vehicles_per_hour=1800,project_id=pid,fresh_day=True,coverage_only=True,
                  traffic_estimates=setup.get('traffic_estimates',{}),traffic_manual=setup.get('vehicles_per_hour'))
        write_json(directory/'state.json',dict(id=cid,status='coverage',spec=spec,created_at=batch['created_at'],message='本轮全库存00:00–24:00模拟'))
        project['simulation_batch']=batch;project['result']=None;store.save(path,project)
        return batch


def inspect(root,project,threshold=60,require_ready=False):
    from .investment import summarize
    batch=project.get('simulation_batch');ids={f['screen_id'] for f in project['frames'] if f.get('screen_id')}
    evidence=dict(campaign_id=batch['id'] if batch else None,campaign=project.get('ad_setup',{}).get('campaign'),screens={},fingerprint=batch['signature'] if batch else None)
    state={};errors=[]
    current=bool(batch and batch['signature']==signature(project))
    if current:
        path=store.directory(root,project['id'])/('coverage-'+batch['id']);file=path/'state.json'
        if file.exists():
            from .coverage import status
            state=status(root,project['id'],batch['id'])
        for sid,item in state.get('items',{}).items():
            if sid not in ids or item.get('status')!='completed':continue
            try:
                scene_path=path/'scenes'/item['scene_id']
                run_path=Path(root)/'worlds'/item['run_id']/'state.json'
                files=[run_path,scene_path/'base.json']+[scene_path/f'hour-{h}.json' for h in range(1,25)]
                stamps=tuple((f.stat().st_mtime_ns,f.stat().st_size) for f in files)
                row=validated_screen(str(run_path),str(scene_path),sid,batch['created_at'],threshold,stamps)
                evidence['screens'][sid]=row
            except (ValueError,OSError,KeyError) as exc:errors.append(dict(screen_id=sid,error=str(exc)[:200]))
    ready=current and bool(ids) and ids<=evidence['screens'].keys()
    summary=dict(status=state.get('status','not_started') if current else 'not_started',campaign_id=evidence['campaign_id'],direct=len(evidence['screens']),
        done=len(evidence['screens']),total=len(ids),ready=ready,scene_ids=[r['scene_id'] for r in evidence['screens'].values()],
        message=state.get('message','请开始本轮00:00–24:00模拟') if current else '请开始本轮00:00–24:00模拟',failures=errors+[dict(screen_id=sid,error=i.get('error')) for sid,i in state.get('items',{}).items() if i.get('status')=='failed'])
    evidence['batch']=batch
    if require_ready and not ready:raise ValueError(f'本轮全天模拟尚未完成（{len(evidence["screens"])}/{len(ids)}）。须从00:00完整运行24小时后才能生成第四步报告，不能用历史结果或预测替代。')
    return summary,evidence


@lru_cache(maxsize=512)
def validated_screen(run_path,scene_path,sid,created_at,threshold,stamps):
    """Cache immutable completed results; every poll checks all artifact timestamps."""
    from .investment import summarize
    run=read_json(Path(run_path));path=Path(scene_path)
    if run.get('started_at',0)<created_at or not full_day(run):raise ValueError('不是本轮完整24小时运行')
    base=read_json(path/'base.json')
    if base['meta'].get('run_id')!=run['id']:raise ValueError('场景运行ID不一致')
    for hour in range(1,25):
        frame=read_json(path/f'hour-{hour}.json')
        if frame.get('round')!=hour:raise ValueError('小时记录不完整')
    row=summarize(base,threshold).get(sid)
    if not row:raise ValueError('运行未包含此屏幕')
    return row
