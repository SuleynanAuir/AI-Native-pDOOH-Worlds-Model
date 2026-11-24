"""Recover a missing replay shard from the SAME saved OASIS run, never another hour."""
import threading
from pathlib import Path
from .world import read_json
from .campaign import write_compact,scene_people
from .traffic_network import connected_vehicles,route_pool
_lock=threading.Lock()


def campaign_hour(path,round_num,uploads):
    target=path/f'hour-{round_num}.json'
    try:return read_json(target)
    except (ValueError,FileNotFoundError):pass
    with _lock:
        try:return read_json(target)
        except (ValueError,FileNotFoundError):pass
        base=read_json(path/'base.json');sid=base['meta']['id'];rid=base['meta'].get('run_id')
        if not rid:raise ValueError('该小时记录损坏，且缺少原始运行，需重新模拟此场景')
        source=Path(uploads)/'scene_library'/sid
        run=read_json(Path(uploads)/'worlds'/rid/'state.json')
        if run['status']!='completed':raise ValueError('原始运行尚未完成，不能修复回放')
        try:hour=read_json(source/f'hour-{round_num}.json')
        except (ValueError,FileNotFoundError):
            from .traffic import build_traffic
            frames=build_traffic(run['scene'],run['scene']['traffic_options'],run['snapshots'])['frames']
            hour=next(f for f in frames if f['round']==round_num)
            write_compact(source/f'hour-{round_num}.json',hour)
        saved=next((h for h in base.get('traffic',{}).get('hourly',[]) if h['round']==round_num),None)
        if not saved:raise ValueError('该小时缺少原始车流参数，请重新生成场景；不会借用其他小时')
        slot=run['scene']['schedule'][round_num-1];seed=run['scene']['seed'];network=base['network'];policies=base['traffic'].get('policies',[])
        cars=connected_vehicles(slot,seed,saved.get('requested_vehicles',saved['vehicles']),network,policies,route_pool(network,seed,policies),absolute_count=saved.get('absolute_hourly',True))
        value={**hour,'vehicles':cars,'recovered_from_run':rid}
        write_compact(target,value)
        return value
