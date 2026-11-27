"""Read-only, hour-sharded views of independent runs; no cross-scene population totals."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import shutil
import threading
import uuid
from .world import read_json,write_json
from .traffic import build_traffic

_lock=threading.Lock()


def location_key(scene):
    point=scene.get('geographic_context',{}).get('coordinate')
    return (f"{point['lat']},{point['lon']}" if point else scene.get('scene_label',''))


def publish(root,scene,traffic,source_type,run_id=None,variant=""):
    """Stage immutable views and rename atomically; clients never see half-built scenes."""
    if source_type not in ('oasis','preview'):raise ValueError('场景来源无效')
    identifier=hashlib.sha256(('oasis:'+run_id+variant).encode()).hexdigest()[:32] if run_id else uuid.uuid4().hex
    root=Path(root);root.mkdir(parents=True,exist_ok=True);target=root/identifier
    with _lock:
        if (target/'meta.json').exists():return read_json(target/'meta.json')
        stage=root/('.'+uuid.uuid4().hex);stage.mkdir()
        try:
            context=scene.get('geographic_context',{});frame=context.get('frame',{});schedule=scene.get('schedule') or [dict(round=i+1,day=1,hour=i%24,time=f'{i%24:02}:00',period_label='场景时段') for i in range(scene['rounds'])]
            meta=dict(id=identifier,title=scene['scene_label'],source_type=source_type,run_id=run_id,
                      source_label=('快速策略仿真 · 非逐小时模型决策' if scene.get('decision_method')=='policy_simulation_v1' else '批量模型推演回放' if scene.get('decision_method')=='batched_interviews_v2' else 'OASIS 批量推演回放' if scene.get('decision_method')=='batched_interviews_v1' else 'OASIS 已完成回放') if source_type=='oasis' else '地图人群预览 · 未运行 OASIS 决策',
                      decision_method=scene.get('decision_method','individual_interviews' if source_type=='oasis' else 'preview'),
                      location_key=location_key(scene),coordinate=context.get('coordinate'),screen_id=frame.get('screen_id'),
                      agent_count=scene['agent_count'],total_population=scene['total_population'],rounds=scene['rounds'],
                      group_count=len(scene['groups']),created_at=datetime.now(timezone.utc).isoformat(),
                      schedule=[{k:s.get(k) for k in ('round','day','date','hour','time','period_label')} for s in schedule],
                      caveat='每格为独立实验；人数、车辆和曝光不可相加视作去重覆盖；日期按各格记录展示。')
            # Keep geometry, sources and counts. Do not duplicate full prompts or all 24 hours.
            base=dict(meta=meta,locality=scene.get('locality',{}),network=scene['neighborhood'],screens=traffic['screens'],groups=scene['groups'],events=traffic['events'])
            write_json(stage/'base.json',base)
            for hourly in traffic['frames']:write_json(stage/f'hour-{hourly["round"]}.json',hourly)
            write_json(stage/'meta.json',meta);stage.rename(target)
        except Exception:
            shutil.rmtree(stage,ignore_errors=True);raise
    return meta


def import_run(root,run_directory,pedestrians_only=False):
    state=read_json(Path(run_directory)/'state.json')
    if state['status']!='completed':raise ValueError('只能加入已完成的 OASIS 运行；进行中的运行请等待完成')
    rid=state['id'];variant=':pedestrians' if pedestrians_only else '';identifier=hashlib.sha256(('oasis:'+rid+variant).encode()).hexdigest()[:32]
    target=Path(root)/identifier/'meta.json'
    if target.exists():return read_json(target)
    scene={**state['scene'],'decision_method':state.get('decision_method','individual_interviews')}
    if not scene.get('neighborhood'):raise ValueError('该旧运行没有可比较的路网')
    options={**scene['traffic_options'],'vehicles_per_hour':0} if pedestrians_only else scene['traffic_options']
    signature=hashlib.sha256(json.dumps(dict(options=options,round=state['current_round'],version=2),sort_keys=True).encode()).hexdigest()[:20]
    cache=Path(run_directory)/f'traffic-{signature}.json'
    traffic=read_json(cache) if cache.exists() else build_traffic(scene,options,state['snapshots'])
    return publish(root,scene,traffic,'oasis',rid,variant=variant)


def directory(root,identifier):
    if not isinstance(identifier,str) or len(identifier)!=32 or any(c not in '0123456789abcdef' for c in identifier):raise ValueError('场景 ID 无效')
    path=Path(root)/identifier
    if not (path/'meta.json').exists():raise FileNotFoundError()
    return path
