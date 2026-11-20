import copy
import json
from pathlib import Path
import pytest
from app.audience.campaign import validate_attitudes,validate_request,materialize_scene,road_policies
from app.audience.campaign_research import public_url,validate_campaign,research,PRESETS
from app.audience.traffic_network import route_pool,connected_vehicles
from app.audience.world import read_json,write_json


def road_network():
    return dict(meters_per_unit=1,view_radius=80,vehicle_paths=[
        dict(points=[dict(x=100,y=295),dict(x=400,y=295),dict(x=700,y=295),dict(x=950,y=295)],tags={'highway':'primary','name':'Main','oneway':'yes'}),
        dict(points=[dict(x=400,y=295),dict(x=400,y=100)],tags={'highway':'residential','name':'Side'}),
        dict(points=[dict(x=700,y=295),dict(x=700,y=500)],tags={'access':'private','highway':'service'})])


def test_contiguous_vehicle_routes_oneway_access_and_peaks():
    network=road_network();pool=route_pool(network,42)
    assert pool and max(p['length'] for p in pool)>=500
    assert all(not any(p['y']==500 for p in route['points']) for route in pool)
    for r in pool:
        for a,b in zip(r['points'],r['points'][1:]):
            if a['y']==b['y']==295:assert a['x']<b['x']
    peak=connected_vehicles(dict(round=9,period='morning'),42,1800,network,pool=pool)
    quiet=connected_vehicles(dict(round=1,period='quiet'),42,1800,network,pool=pool)
    assert len(peak)==2700 and len(quiet)==324
    assert sum(v['journey']['start_minute']<=23<=v['journey']['end_minute'] for v in peak)>20
    assert all(0<=v['journey']['start_minute']<v['journey']['end_minute']<60 for v in peak)
    assert peak==connected_vehicles(dict(round=9,period='morning'),42,1800,network,pool=pool)
    assert connected_vehicles(dict(round=1),42,0,network)==[]
    assert connected_vehicles(dict(round=1),42,100,dict(meters_per_unit=1,vehicle_paths=[]))==[]


def test_restricted_road_does_not_get_private_cars():
    network=road_network();network['vehicle_paths']=network['vehicle_paths'][:1]
    cars=connected_vehicles(dict(round=1),3,100,network,[dict(road='Main',allowed=['bus','taxi'])])
    assert cars and {c['kind'] for c in cars}<= {'bus','taxi'}


def test_model_scores_unknown_and_references_validated():
    people=[dict(id=1),dict(id=2)];rows=[dict(agent_id=1,interest=0,favorability=100,reason='假设需求与创意相关',confidence='low',source_ids=['R1']),dict(agent_id=2,interest=None,favorability=None,reason='资料不足',confidence='low',source_ids=['R1'])]
    assert validate_attitudes({'agents':rows},people,{'R1'})==rows
    for mutate in [lambda r:r.pop(),lambda r:r[0].update(interest=101),lambda r:r[0].update(interest=True),lambda r:r[0].update(favorability=float('nan')),lambda r:r[1].update(agent_id=1),lambda r:r[0].update(source_ids=['invented'])]:
        invalid=copy.deepcopy(rows);mutate(invalid)
        with pytest.raises(ValueError):validate_attitudes({'agents':invalid},people,{'R1'})


@pytest.mark.parametrize('url',['http://example.com','https://localhost/a','https://127.0.0.1','https://[::1]','https://192.168.1.1','https://example.com:9000','https://user:pass@example.com'])
def test_non_public_research_urls_rejected(url):
    with pytest.raises(ValueError):public_url(url,resolve=False)


def test_live_retrieval_never_accepts_invented_selected_sources():
    def fetch(url):return dict(url=url,title='Official',published_at=None,retrieved_at='2026-11-20',text='Content',links=[('/releases/verified','Verified running article')])
    def model(*args,**kwargs):return {'selected_ids':['C404']}
    with pytest.raises(ValueError,match='不存在'):research(PRESETS[0],[],{},fetcher=fetch,model=model)


def test_materialization_does_not_mutate_native_events(tmp_path):
    source=tmp_path/'source';source.mkdir();write_json(source/'hour-1.json',dict(round=1,pedestrians=[],vehicles=[]))
    base=dict(_path=source,meta={'id':'a'*32,'rounds':1,'coordinate':{}},network=road_network(),screens=[dict(id='screen',x=500,y=295)],events=[dict(id='old',kind='pedestrian',actor_id='p-1-0',screen_id='screen',round=1,minute=2,count=300,units=1)])
    before=copy.deepcopy(base);evidence=dict(campaign=PRESETS[0],sources=[]);analysis={'agents':{'1':{'interest':70}},'groups':[]}
    materialize_scene(tmp_path/'overlay',base,[],{},[dict(round=1,hour=8,period='morning')],42,evidence,analysis,100)
    output=read_json(tmp_path/'overlay'/'base.json')
    assert base==before and output['events'][0]['kind'] in ('pedestrian','vehicle')
    assert [e for e in output['events'] if e['kind']=='pedestrian']==base['events']
    assert output['traffic']['calibration']=='uncalibrated'
    assert output['screens'][0]['creative']=='NIKE RUNNING'
    assert read_json(source/'hour-1.json')['vehicles']==[]


def test_experiment_api_rejects_partial_or_unrelated_overlays(tmp_path,monkeypatch):
    from app import create_app
    from app.audience import campaign
    app=create_app();app.config.update(TESTING=True,UPLOAD_FOLDER=str(tmp_path));client=app.test_client()
    jid='b'*32;sid='a'*32;other='c'*32;root=tmp_path/'campaign_experiments'/jid;root.mkdir(parents=True)
    for s in [sid,other]:
        d=tmp_path/'scene_library'/s;d.mkdir(parents=True);write_json(d/'meta.json',dict(id=s))
    state=dict(id=jid,status='running',created_at='2026-11-20',spec=dict(campaign=PRESETS[0],scene_ids=[sid],vehicles_per_hour=1800))
    write_json(root/'state.json',state)
    assert client.get('/api/world/campaign-experiments/'+jid+'/scenes/'+sid).status_code==400
    assert client.get('/api/world/campaign-experiments/latest').json['data'] is None
    state['status']='completed';write_json(root/'state.json',state)
    assert client.get('/api/world/campaign-experiments/'+jid+'/scenes/'+other).status_code==400
    assert client.post('/api/world/campaign-experiments/'+jid+'/traffic',json={'vehicles_per_hour':3001}).status_code==400
    assert client.post('/api/world/campaign-experiments/'+jid+'/traffic',json={'vehicles_per_hour':100,'scene_ids':[other]}).status_code==400
    calls=[]
    def fake_start(*args):calls.append(args);return {'id':'d'*32,'status':'queued'}
    monkeypatch.setattr(campaign,'start_job',fake_start)
    response=client.post('/api/world/campaign-experiments/'+jid+'/traffic',json={'vehicles_per_hour':0,'campaign':{'brand':'tampered'}})
    assert response.status_code==202
    assert calls[0][3]['campaign']['brand']=='Nike' and calls[0][3]['vehicles_per_hour']==0 and calls[0][-1]==jid
    assert read_json(root/'state.json')==state


def test_map_tessellation_not_mistaken_for_signal_stops():
    network=dict(meters_per_unit=1,vehicle_paths=[dict(points=[dict(x=x,y=295) for x in range(0,950,2)],tags={'oneway':'yes','highway':'primary'})])
    pool=route_pool(network,42)
    assert pool and max(r['length'] for r in pool)>=650
    assert all(len(r['points'])==2 and not r['junctions'] for r in pool)
