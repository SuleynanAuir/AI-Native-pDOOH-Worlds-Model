"""Audit generated traffic opportunities against exported journeys and original weights."""
import json
from collections import Counter
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.audience.traffic import opportunities


def verify(traffic,state):
    if 'traffic_replay' in traffic:traffic=traffic['traffic_replay']
    assert traffic['source_run_id']==state['id']
    scene=state['scene'];expected=[];pedestrians=vehicles=0;styles=set();types=set()
    totals={s['id']:dict(name=s['name'],pedestrian=0,vehicle=0,vehicle_passages=0,total=0) for s in traffic['screens']}
    assert len(traffic['frames'])==scene['rounds']
    parents={a['id']:a for a in scene['agents']}
    for frame in traffic['frames']:
        round_num=frame['round'];weights=Counter()
        scheduled=scene['mobility_rounds'][round_num-1]
        ids=set()
        for kind,key in [('pedestrian','pedestrians'),('vehicle','vehicles')]:
            for actor in frame[key]:
                assert actor['id'] not in ids;ids.add(actor['id'])
                points=actor['journey']['waypoints']
                assert all(a['minute']<=b['minute'] for a,b in zip(points,points[1:]))
                assert 0<=points[0]['minute']<points[-1]['minute']<60
                if kind=='pedestrian':
                    count=actor['represented_population'];assert count>0
                    weights[actor['parent_agent_id']]+=count;pedestrians+=1;styles.add(actor['appearance'])
                else:
                    count=actor['occupants'];assert 1<=count<=30
                    vehicles+=1;types.add(actor['kind'])
                for encounter in opportunities(points,traffic['screens'],scene['neighborhood']['view_radius']):
                    expected.append(dict(**encounter,id=f'{round_num}:{actor["id"]}:{encounter["screen_id"]}',round=round_num,actor_id=actor['id'],kind=kind,count=count,units=1))
        assert weights=={int(aid):parents[int(aid)]['represented_population'] for aid in scheduled}
        assert sum(weights.values())==frame['represented_pedestrians']
    expected.sort(key=lambda e:(e['round'],e['minute'],e['id']))
    assert traffic['events']==expected
    assert len({e['id'] for e in expected})==len(expected)
    for e in expected:
        row=totals[e['screen_id']];row[e['kind']]+=e['count'];row['total']+=e['count']
        if e['kind']=='vehicle':row['vehicle_passages']+=1
    return dict(source_run_id=state['id'],original_agents=scene['agent_count'],population=scene['total_population'],hours=len(traffic['frames']),
                expansion=traffic['options'],pedestrian_outings=pedestrians,vehicle_outings=vehicles,vehicle_types=sorted(types),visual_variants=sorted(styles),
                passage_events=len(expected),simulated_impression_opportunities=sum(e['count'] for e in expected),by_screen=totals,
                note='模拟曝光机会，非实测观看或去重人数；步行与车辆为不同情景样本。',
                verified=['integer parent weight conservation per hour','all event coordinates and times recomputed','one event per outing and screen','vehicle occupant accounting','original OASIS provenance preserved'])


if __name__=='__main__':
    print(json.dumps(verify(json.loads(Path(sys.argv[1]).read_text()),json.loads(Path(sys.argv[2]).read_text())),ensure_ascii=False,indent=2))
