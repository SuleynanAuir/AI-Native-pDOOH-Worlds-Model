import json
from collections import Counter
import pytest
from app import create_app
from app.audience.world import scene,write_json
from app.audience.traffic import build_traffic,vehicles,validate_traffic,opportunities


@pytest.fixture(scope='module')
def source():return scene(population=20,total_population=2000,rounds=2)


def test_expansion_conserves_population_and_creates_independent_routes(source):
    output=build_traffic(source,dict(pedestrians_per_agent=4,vehicles_per_hour=60))
    assert output==build_traffic(source,dict(pedestrians_per_agent=4,vehicles_per_hour=60))
    assert len(output['screens'])==5
    assert len(output['frames'][0]['pedestrians'])==80
    for frame in output['frames']:
        weights=Counter()
        for p in frame['pedestrians']:weights[p['parent_agent_id']]+=p['represented_population']
        assert weights=={p['id']:p['represented_population'] for p in source['agents']}
        assert frame['represented_pedestrians']==source['total_population']
        assert len({p['appearance'] for p in frame['pedestrians']})==6
        assert len({p['journey']['start_minute'] for p in frame['pedestrians']})>60
        for p in frame['pedestrians']:
            if p['id'].endswith('-0'):assert p['journey']==source['mobility_rounds'][frame['round']-1][str(p['parent_agent_id'])]
    ids=[e['id'] for e in output['events']]
    assert len(ids)==len(set(ids))
    assert {e['kind'] for e in output['events']}=={'pedestrian','vehicle'}
    for frame in output['frames']:
        subjects={p['id']:p['represented_population'] for p in frame['pedestrians']}
        subjects.update({v['id']:v['occupants'] for v in frame['vehicles']})
        for event in (e for e in output['events'] if e['round']==frame['round']):assert event['count']==subjects[event['actor_id']]


def test_small_population_never_creates_zero_weight_copies():
    output=build_traffic(scene(population=20,total_population=21,rounds=1),dict(pedestrians_per_agent=10,vehicles_per_hour=0))
    actors=output['frames'][0]['pedestrians']
    assert len(actors)==21 and all(a['represented_population']==1 for a in actors)
    assert output['frames'][0]['vehicles']==[]
    assert all(e['kind']=='pedestrian' for e in output['events'])


def test_vehicle_lanes_arrivals_types_and_peak_volume():
    morning=vehicles(dict(round=8,period='morning'),42,180)
    quiet=vehicles(dict(round=1,period='quiet'),42,180)
    assert len(morning)>len(quiet)>0
    assert {v['kind'] for v in morning}=={'car','taxi','bus','van'}
    for v in morning:
        start,end=v['journey']['waypoints']
        assert 0<=start['minute']<end['minute']<60
        assert start['y']==end['y']==(346 if v['direction']==1 else 374)
        assert (end['x']-start['x'])*v['direction']>0
        assert 1<=v['occupants']<=30
    for direction in (-1,1):
        lane=[v for v in morning if v['direction']==direction]
        assert len({v['speed_kmh'] for v in lane})==1
        assert all(a['journey']['start_minute']<b['journey']['start_minute'] for a,b in zip(lane,lane[1:]))


def test_passage_once_per_board_and_no_false_far_exposure():
    points=[dict(x=0,y=0,minute=0),dict(x=100,y=0,minute=5),dict(x=0,y=0,minute=10)]
    events=opportunities(points,[dict(id='near',x=50,y=10),dict(id='far',x=50,y=100)],20)
    assert len(events)==1 and events[0]['screen_id']=='near'
    assert events[0]['minute']==2.5


@pytest.mark.parametrize('value',[[],{'vehicles_per_hour':-1},{'vehicles_per_hour':3001},{'vehicles_per_hour':True},{'pedestrians_per_agent':11},{'pedestrians_per_agent':0},{'pedestrians_per_agent':2.5}])
def test_invalid_settings_rejected(value):
    with pytest.raises(ValueError):validate_traffic(value)


def test_replay_endpoint_preserves_native_records_and_caches(tmp_path,source):
    app=create_app();app.config.update(TESTING=True,UPLOAD_FOLDER=str(tmp_path));client=app.test_client()
    rid='b'*32;directory=tmp_path/'worlds'/rid;directory.mkdir(parents=True)
    path=directory/'state.json';state=dict(id=rid,status='completed',scene=source,current_round=2,snapshots=[])
    write_json(path,state);before=path.read_bytes();stamp=path.stat().st_mtime_ns
    response=client.post(f'/api/world/runs/{rid}/traffic',json={'traffic_options':{'vehicles_per_hour':0,'pedestrians_per_agent':2}})
    assert response.status_code==200 and response.json['data']['source_run_id']==rid
    repeated=client.post(f'/api/world/runs/{rid}/traffic',json={'traffic_options':{'vehicles_per_hour':0,'pedestrians_per_agent':2}})
    assert repeated.json==response.json
    assert path.read_bytes()==before and path.stat().st_mtime_ns==stamp
    assert len(list(directory.glob('traffic-*.json')))==1
    assert client.post(f'/api/world/runs/{rid}/traffic',json={'traffic_options':{'vehicles_per_hour':3001}}).status_code==400


def test_traffic_preview_is_available_without_llm_key(tmp_path):
    app=create_app();app.config.update(TESTING=True,UPLOAD_FOLDER=str(tmp_path),LLM_API_KEY=None)
    response=app.test_client().post('/api/world/traffic-preview',json=dict(agent_count=20,total_population=2000,rounds=1,traffic_options=dict(pedestrians_per_agent=2,vehicles_per_hour=0)))
    assert response.status_code==200
    data=response.json['data']
    assert len(data['frames'])==1 and len(data['frames'][0]['pedestrians'])==40
    assert data['frames'][0]['vehicles']==[]
    assert not list(tmp_path.glob('worlds/*/state.json'))
