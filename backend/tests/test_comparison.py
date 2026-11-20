"""Offline contract checks for independent, immutable multi-scene replay views."""
import copy
import json
from pathlib import Path
import pytest
from app import create_app
from app.audience import comparison
from app.audience.world import scene,write_json,read_json
from app.audience.traffic import build_traffic
from test_geolocation import fixture_context


def fixture_scene():
    context=fixture_context()
    return scene(population=20,total_population=2000,rounds=2,geographic_context=context,locality=context['locality'])


def test_scene_assets_keep_counts_sources_and_separate_hours(tmp_path):
    s=fixture_scene();t=build_traffic(s,dict(pedestrians_per_agent=2,vehicles_per_hour=10))
    a=comparison.publish(tmp_path,s,t,'preview')
    other=copy.deepcopy(s);other['scene_label']='Another offline scene';other['geographic_context']['coordinate']['lon']+=1
    b=comparison.publish(tmp_path,other,t,'preview')
    assert a['id']!=b['id'] and a['location_key']!=b['location_key']
    assert a['source_type']=='preview' and '未运行' in a['source_label']
    base=read_json(tmp_path/a['id']/'base.json')
    assert base['events']==t['events'] and base['network']==s['neighborhood']
    assert 'mobility_rounds' not in base and 'snapshots' not in base
    assert read_json(tmp_path/a['id']/'hour-1.json')==t['frames'][0]
    assert read_json(tmp_path/a['id']/'hour-2.json')==t['frames'][1]
    assert a['agent_count']==20 and a['total_population']==2000


def test_import_is_idempotent_and_does_not_modify_original_run(tmp_path):
    d=tmp_path/'run';d.mkdir();s=fixture_scene()
    state=dict(id='a'*32,status='completed',scene=s,current_round=2,snapshots=[])
    write_json(d/'state.json',state);before=(d/'state.json').read_bytes()
    first=comparison.import_run(tmp_path/'library',d);again=comparison.import_run(tmp_path/'library',d)
    assert first==again and first['source_type']=='oasis' and first['run_id']==state['id']
    assert len(list((tmp_path/'library').glob('*/meta.json')))==1
    assert (d/'state.json').read_bytes()==before
    state['status']='running';write_json(d/'state.json',state)
    with pytest.raises(ValueError,match='已完成'):comparison.import_run(tmp_path/'library',d)


def test_hour_api_rejects_out_of_range_and_path_traversal(tmp_path):
    app=create_app();app.config.update(TESTING=True,UPLOAD_FOLDER=str(tmp_path),LOCATION_LOOKUP_ENABLED=False)
    s=fixture_scene();t=build_traffic(s,dict(pedestrians_per_agent=1,vehicles_per_hour=0));meta=comparison.publish(tmp_path/'scene_library',s,t,'preview')
    client=app.test_client();url='/api/world/comparison-scenes/'+meta['id']
    assert client.get('/api/world/comparison-scenes').json['data']==[meta]
    assert client.get(url).json['data']['meta']['id']==meta['id']
    assert client.get(url+'/hours/1').json['data']==t['frames'][0]
    assert client.get(url+'/hours/0').status_code==400
    assert client.get(url+'/hours/3').status_code==400
    with pytest.raises(ValueError):comparison.directory(tmp_path,'../secrets')
    with pytest.raises(FileNotFoundError):comparison.directory(tmp_path,'f'*32)
    assert client.post('/api/world/comparison-scenes/import',json={'run_id':17}).status_code==400
    assert client.post('/api/world/comparison-scenes/preview',json={'agent_count':20}).status_code==400


def test_summary_poll_does_not_send_replay_payload(tmp_path):
    app=create_app();app.config.update(TESTING=True,UPLOAD_FOLDER=str(tmp_path))
    rid='c'*32;path=tmp_path/'worlds'/rid;path.mkdir(parents=True)
    write_json(path/'state.json',dict(id=rid,status='completed',current_round=24,llm_decisions=42,scene={'large':'x'*100000},snapshots=['x'*100000]))
    response=app.test_client().get('/api/world/runs/'+rid+'/summary')
    assert response.status_code==200 and response.json['data']['id']==rid
    assert response.json['data']['current_round']==24
    assert 'scene' not in response.json['data'] and len(response.data)<1000
