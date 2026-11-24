import base64
from io import BytesIO
import pytest
from app import create_app
from app.audience.ad_setup import estimate_traffic,core_regions
from app.audience.campaign import scene_flow,hourly_flow


def frame():return {'screen_id':'s','lat':37.7,'lon':-122.4,'fields':{'ADDRESS_LOCALITY':'Test','CLOSEST_POI':'Shop'}}
def evidence(area,config):
    return {'roads':[{'id':'road-main','name':'Main','incoming_portals':2,'reference_ids':['ref1']}],'references':[{'id':'ref1','daily_vehicles':10000}]}

def model(config,system,payload,**kwargs):
    assert payload['region']['coordinate']['lat']==37.7
    return {'road_estimates':[{'road_id':'road-main','daily_entries':4800,'low':2400,'high':9600,'reference_ids':['ref1'],'reason':'历史计数迁移假设'}],'hourly_weights':[{'hour':h,'weight':1} for h in range(24)],'reason':'区域推测','uncertainties':['没有实测']}

def estimate(frames,config=None,m=model):return estimate_traffic(frames,config or {},m,evidence_loader=evidence)

def test_traffic_evidence_and_flow_application():
    rows=estimate([frame()]);e=rows['s']
    assert e['calibration']=='evidence_informed_not_field_calibrated'
    assert e['method_version']==3 and len(e['hourly'])==24
    assert sum(r['vehicles_per_hour'] for r in e['hourly'])==4800
    spec={'traffic_estimates':rows,'vehicles_per_hour':1800}
    flow,e=scene_flow(spec,{'meta':{'screen_id':'s'}})
    assert hourly_flow(flow,e,8)==(200,True,'llm_hourly_estimate')
    assert scene_flow(spec,{'meta':{'screen_id':'other'}})[1]['kind']=='default_scenario'
    spec['traffic_manual']=0
    assert scene_flow(spec,{'meta':{'screen_id':'s'}})[0]==0

@pytest.mark.parametrize('error',['short','duplicate','range','bool','mixed_null','source','road_id','zero_weights'])
def test_traffic_rejects_incomplete_or_invalid_hours(error):
    def bad(*a,**kw):
        r=model(*a,**kw);rows=r['hourly_weights'];road=r['road_estimates'][0]
        if error=='short':rows.pop()
        if error=='duplicate':rows[1]['hour']=0
        if error=='range':road['high']=10
        if error=='bool':road['daily_entries']=True
        if error=='mixed_null':road['low']=None
        if error=='source':road['reference_ids']=['invented']
        if error=='road_id':road['road_id']='invented'
        if error=='zero_weights':
            for row in rows:row['weight']=0
        return r
    with pytest.raises(ValueError):estimate([frame()],m=bad)

def test_unknown_zero_and_high_volume_are_distinct():
    for total in (None,0,96000):
        def changed(*a,**kw):
            r=model(*a,**kw);r['road_estimates'][0].update(low=total,high=total,daily_entries=total);return r
        e=estimate([frame()],m=changed)['s']
        assert e['hourly'][0]['vehicles_per_hour']==(None if total is None else total//24)
        if total==96000:assert hourly_flow(1800,e,2)==(4000,True,'llm_hourly_estimate')
        if total is None:assert hourly_flow(1800,e,0)[2]=='unknown_hour_default_scenario'

def test_region_clustering_is_stable_and_shared():
    frames=[frame(),{**frame(),'screen_id':'t','lat':37.7001}]
    assert core_regions(frames)==core_regions(list(reversed(frames)))
    rows=estimate(frames);assert rows['s']==rows['t']
    with pytest.raises(ValueError):estimate([{**frame(),'lat':None}])

def test_weighted_samples_preserve_volume_and_do_not_multiply_peaks():
    from app.audience.traffic_network import connected_vehicles
    route={'length':100,'points':[{'x':0,'y':0},{'x':1,'y':0}],'allowed':['car'],'junctions':[],'roads':['test']}
    slot={'round':8,'period':'morning','activity_factor':2};network={'meters_per_unit':100}
    for target in (0,10,3001,12001):
        cars=connected_vehicles(slot,42,target,network,pool=[route],absolute_count=True)
        assert len(cars)==min(3000,target)
        assert sum(c['represented_vehicles'] for c in cars)==target
    assert len(connected_vehicles(slot,42,10,network,pool=[route]))==30

def test_boundary_crossings_not_internal_segments():
    from app.audience.traffic_evidence import boundary_roads
    a={'coordinate':{'lat':0,'lon':0},'radius_m':400}
    features=[{'id':'a','tags':{'name':'Main','highway':'primary','oneway':'yes'},'geometry':[{'lat':0,'lon':-.01},{'lat':0,'lon':0},{'lat':0,'lon':.01}]}]
    roads=boundary_roads(a,features+features)
    assert roads[0]['incoming_portals']==1
    features[0]['tags']['oneway']='no'
    assert boundary_roads(a,features)[0]['incoming_portals']==2
    features[0]['tags']['motor_vehicle']='no'
    assert boundary_roads(a,features)==[]


def test_project_setup_and_creative_upload(tmp_path,monkeypatch):
    app=create_app();app.config.update(TESTING=True,UPLOAD_FOLDER=str(tmp_path));client=app.test_client()
    p=client.post('/api/planning/sample',json={'source_sheet':'FilteredFrames'}).json['data'];url='/api/planning/'+p['id']
    from app.audience.campaign_research import PRESETS
    assert client.post(url+'/ad-setup',json={'campaign':PRESETS[0],'vehicles_per_hour':None}).status_code==200
    assert client.get(url+'/ad-setup').json['data']['campaign']['brand']=='Nike'
    assert client.post(url+'/ad-setup',json={'campaign':PRESETS[0],'vehicles_per_hour':-1}).status_code==400
    raw=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a/aUAAAAASUVORK5CYII=')
    upload=client.post(url+'/creative',data={'image':(BytesIO(raw),'ad.png')},content_type='multipart/form-data')
    assert upload.status_code==200
    asset=upload.json['data'];assert client.get(asset['url']).data==raw
    monkeypatch.setattr('app.audience.ad_setup.describe_creative',lambda *a:{'description':'Fixture ad visual','model':'fixture'})
    assert client.post(url+'/creative/analyze').json['data']['description']=='Fixture ad visual'
    def fake_estimate(frames,config):
        return {f['screen_id']:{'screen_id':f['screen_id'],'vehicles_per_hour':300} for f in frames}
    monkeypatch.setattr('app.audience.ad_setup.estimate_traffic',fake_estimate)
    sid=p['frames'][0]['screen_id']
    assert client.post(url+'/traffic-estimate',json={'screen_ids':[sid]}).status_code==200
    saved=client.get(url+'/ad-setup').json['data']
    assert saved['traffic_estimates'][sid]['vehicles_per_hour']==300
    assert saved['creative']['id']==asset['id']

    monkeypatch.setattr('app.audience.campaign.directory',lambda *a:tmp_path)
    monkeypatch.setattr('app.audience.campaign.start_job',lambda root,library,worlds,spec,config: {'spec':spec})
    response=client.post('/api/world/campaign-experiments',json={'project_id':p['id'],'scene_ids':['a'*32],'campaign':PRESETS[1],'vehicles_per_hour':1800})
    assert response.status_code==202
    spec=response.json['data']['spec']
    assert spec['campaign']['title']==PRESETS[0]['title']
    assert spec['campaign']['creative_observation']=='Fixture ad visual'
    assert spec['traffic_estimates'][sid]['vehicles_per_hour']==300


def test_official_counts_are_geographically_scoped(tmp_path,monkeypatch):
    from app.audience import traffic_evidence as te
    area={'coordinate':{'lat':37.77,'lon':-122.42},'radius_m':400}
    raw={'features':[],'reverse':{'address':{'city':'San Francisco'}},'queried_at':'test'}
    monkeypatch.setattr(te,'map_evidence',lambda *a:raw)
    monkeypatch.setattr(te,'boundary_roads',lambda *a:[{'id':'road-3rdst','name':'3rd Street','incoming_portals':2}])
    config={'LOCATION_LOOKUP_ENABLED':True,'UPLOAD_FOLDER':str(tmp_path)}
    evidence=te.ground_region(area,config)
    assert evidence['references'] and all(r['year']==2025 for r in evidence['references'])
    assert all(r['match']=='same_named_corridor_not_verified_same_segment' for r in evidence['references'])
    raw['reverse']['address']['city']='Oakland'
    assert te.ground_region(area,config)['references']==[]


def test_weighted_vehicle_exposures_survive_materialization(tmp_path,monkeypatch):
    from app.audience import campaign as c
    monkeypatch.setattr(c,'road_policies',lambda *a:[])
    monkeypatch.setattr(c,'route_pool',lambda *a:[])
    monkeypatch.setattr(c,'read_json',lambda *a:{'pedestrians':[]})
    monkeypatch.setattr(c,'connected_vehicles',lambda *a,**kw:[{'id':'v','occupants':2,'represented_vehicles':7,'journey':{'waypoints':[],'start_minute':0,'end_minute':1}}])
    monkeypatch.setattr(c,'opportunities',lambda *a:[{'screen_id':'s','minute':1}])
    base={'_path':tmp_path,'events':[],'screens':[{'id':'s'}],'network':{'view_radius':100},'meta':{'id':'test'}}
    c.materialize_scene(tmp_path/'out',base,[],{},[{'round':1,'hour':0}],42,{'campaign':{'title':'test','message':'test'}},{'agents':{}},7)
    import json
    output=json.loads((tmp_path/'out'/'base.json').read_text())
    assert output['events'][0]['count']==14 and output['events'][0]['units']==7
    assert output['traffic']['hourly'][0]['vehicles']==7
    assert output['traffic']['hourly'][0]['rendered_samples']==1


def test_incomplete_map_cache_is_refetched(tmp_path):
    from app.audience.mapricot_provider import cached
    import hashlib,json
    signature=['test']
    p=tmp_path/(hashlib.sha256(json.dumps(signature,sort_keys=True).encode()).hexdigest()+'.json')
    p.write_text('')
    assert cached(tmp_path,signature,lambda:{'valid':'map'})=={'valid':'map'}
    assert json.loads(p.read_text())=={'valid':'map'}
    assert cached(tmp_path,signature,lambda:1)=={'valid':'map'}
