import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from app import create_app
from app.audience import geolocation as geo
from app.audience.geographic_scene import geographic_network
from app.audience.world import scene,write_json
from app.audience.traffic import build_traffic
from app.audience.workbook import read_workbook


@pytest.mark.parametrize('value', ['POINT (-122.4 37.7)','SRID=4326; POINT(-122.4 37.7)','POINT Z (-1.224e2 3.77e1 8)',{'type':'Point','coordinates':[-122.4,37.7]}])
def test_coordinates_order_and_formats(value):
    p=geo.coordinates({'GEOM':value});assert p['lon']==-122.4 and p['lat']==37.7 and p['source']=='GEOM'


@pytest.mark.parametrize('value',['POINT (37.7 -122.4)','SRID=3857;POINT(1 2)','POINT (NaN 3)','LINESTRING (1 2,3 4)',{'type':'Point','coordinates':[True,False]},{'type':'Point','coordinates':[0,float('inf')]},'POINT(181 89)'])
def test_bad_geom_never_falls_back_or_silently_swaps(value):
    with pytest.raises(ValueError):geo.coordinates({'GEOM':value,'LATITUDE':10,'LONGITUDE':20})


def test_coordinate_conflict_preserves_geom_and_warns():
    p=geo.coordinates(dict(GEOM='POINT(20 10)',LATITUDE=11,LONGITUDE=21))
    assert p['lat']==10 and any('30 米' in w for w in p['warnings'])
    assert geo.coordinates(dict(LATITUDE=10,LONGITUDE=20))['source']=='LATITUDE/LONGITUDE'


def test_real_test_workbook_reads_filtered_not_unfiltered():
    root=Path(__file__).resolve().parents[2]
    inventory=geo.filtered_inventory(read_workbook((root/'data/test.xlsx').read_bytes()),'test.xlsx')
    assert inventory['sheet']=='FilteredFrames' and inventory['total']==144 and inventory['valid_coordinates']==144
    assert inventory['frames'][0]['coordinate']['lon']==-122.423367
    assert inventory['frames'][0]['original']['ADDRESS_LOCALITY']=='Sacramento et al'
    with pytest.raises(ValueError,match='FilteredFrames'):geo.filtered_inventory({'UnfilteredFrames':[['VIOOH_ID']]},'x.xlsx')


def fixture_context():
    # Entirely invented coordinates and names for offline tests, not an OSM observation.
    features=[];center=dict(lat=10.,lon=20.,source='GEOM',crs='EPSG:4326',warnings=[])
    for axis in range(2):
        for line in range(4):
            points=[];refs=[]
            for i in range(4):
                row,col=(line,i) if axis==0 else (i,line)
                points.append(dict(lat=10+(row-1.5)*.001,lon=20+(col-1.5)*.001));refs.append(row*4+col+1)
            fid=f'osm-way-{axis*4+line+1}'
            features.append(dict(id=fid,osm_id=axis*4+line+1,osm_type='way',tags=dict(highway='residential',name='离线测试道路'),geometry=points,nodes=refs,distance_m=60,url='https://www.openstreetmap.org/way/1'))
    for i,(tag,name) in enumerate([({'leisure':'park'},'离线测试公园'),({'amenity':'library'},'离线测试图书馆'),({'shop':'supermarket'},'离线测试商店')]):
        features.append(dict(id=f'osm-node-{100+i}',osm_id=100+i,osm_type='node',tags={**tag,'name':name},geometry=[dict(lat=10.0005,lon=20.0005)],nodes=[],distance_m=80,url='https://www.openstreetmap.org/node/100'))
    evidence=dict(reverse=dict(address=dict(country='Testland',city='Test City',suburb='Test Community',road='Test Road'),display_name='离线测试地点，不是真实查证'),features=features,queried_at='2026-01-01T00:00:00Z',radius_m=400,reverse_source='https://example.org/reverse',overpass_source='https://example.org/overpass',attribution='OFFLINE TEST FIXTURE — NOT REAL MAP EVIDENCE',limitations=['仅用于离线测试'])
    frame=dict(screen_id='TEST-01',coordinate=center,warnings=[],city='Wrong Market',country='Testland',address='Test Road',venue='outdoor.billboards.roadside',poi='Unverified POI',original={},fields={},key='filtered-1')
    inference=dict(environment_interpretation='离线模型替身：根据测试道路与设施推演',audience_hypotheses=[dict(name='测试角色'+str(i),rationale='测试依据',source_ids=['osm-way-1']) for i in range(4)],uncertainties=['离线测试，不是实地资料'],model='offline-stub')
    return geo.resolved_context(frame,evidence,inference,'c'*32)


def test_verified_network_changes_scene_and_removes_invented_boards():
    context=fixture_context();network,screens=geographic_network(context)
    assert network['geographic'] and len(network['nodes'])==16
    assert screens[0]['id']=='TEST-01' and screens[0]['x']==500
    assert network['vehicle_paths'] and all(n['id'].startswith('osm-node') for n in network['nodes'])
    assert any('Wrong Market' in w for w in context['warnings'])
    result=scene(population=20,total_population=2000,rounds=2,locality=context['locality'],geographic_context=context)
    assert result['screens']==screens and result['neighborhood']['geographic']
    traffic=build_traffic(result,dict(pedestrians_per_agent=2,vehicles_per_hour=20))
    assert len(traffic['screens'])==1 and traffic['screens'][0]['id']=='TEST-01'
    assert all(v['source'].startswith('OSM') for f in traffic['frames'] for v in f['vehicles'])
    assert all(j['mode']=='walking' for frame in result['mobility_rounds'] for j in frame.values()), 'No mapped transit stop: do not invent boarding'


def test_disabled_lookup_makes_no_requests(tmp_path,monkeypatch):
    app=create_app();app.config.update(TESTING=True,UPLOAD_FOLDER=str(tmp_path),LOCATION_LOOKUP_ENABLED=False)
    def forbidden(*a,**kw):raise AssertionError('Must not send coordinates')
    monkeypatch.setattr(geo,'map_evidence',forbidden)
    client=app.test_client();inventory=client.post('/api/world/geo-inventory',json={}).json['data']
    response=client.post('/api/world/locate-frame',json=dict(inventory_id=inventory['id'],frame_key=inventory['frames'][0]['key']))
    assert response.status_code==409 and response.json['code']=='location_lookup_disabled'
    assert client.get('/api/world/location-config').json['data']['enabled'] is False
    with pytest.raises(ValueError,match='未启用'):geo.request_json('https://example.org',{})


def test_llm_is_given_evidence_and_rejects_invented_refs():
    context=fixture_context();calls=[];output=context['inference'].copy()
    def create(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(finish_reason='stop',message=SimpleNamespace(content=json.dumps(output)))])
    client=SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    result=geo.interpret(context['frame'],context['evidence'],dict(LLM_MODEL_NAME='offline-stub'),client=client)
    assert result['classification']=='model_inference_not_demographics'
    payload=json.loads(calls[0]['messages'][1]['content']);assert payload['map_address']['city']=='Test City'
    assert payload['inventory_hints']['city']=='Wrong Market'
    output['audience_hypotheses'][0]['source_ids']=['made-up-poi']
    with pytest.raises(ValueError,match='未提供'):geo.interpret(context['frame'],context['evidence'],dict(LLM_MODEL_NAME='offline-stub'),client=client)


def test_lookup_route_and_binding_with_offline_provider_stubs(tmp_path,monkeypatch):
    app=create_app();app.config.update(TESTING=True,UPLOAD_FOLDER=str(tmp_path),LOCATION_LOOKUP_ENABLED=True)
    context=fixture_context()
    # Replace both outbound providers. This does not bypass disabled networking in the real app.
    monkeypatch.setattr(geo,'map_evidence',lambda *args:context['evidence'])
    monkeypatch.setattr(geo,'interpret',lambda *args:context['inference'])
    inventory=dict(id='a'*32,filename='offline.xlsx',sheet='FilteredFrames',frames=[context['frame']|dict(error='')])
    root=tmp_path/'geolocations';root.mkdir();write_json(root/('inventory-'+inventory['id']+'.json'),inventory)
    response=app.test_client().post('/api/world/locate-frame',json=dict(inventory_id=inventory['id'],frame_key='filtered-1',radius_m=400))
    assert response.status_code==200
    value=response.json['data'];assert value['locality']['city']=='Test City' and value['network_summary']['nodes']==16
    from app.audience.world_routes import bind_geolocation
    with app.app_context():
        data=dict(locality=value['locality']);bind_geolocation(data);assert data['geographic_context']['id']==value['id']
        data['locality']={**value['locality'],'city':'Different'}
        with pytest.raises(ValueError,match='偏离'):bind_geolocation(data)
        data['locality']={**value['locality'],'sources':[]}
        with pytest.raises(ValueError,match='证据被修改'):bind_geolocation(data)


def test_map_query_is_cached_and_rejects_distant_reverse(tmp_path,monkeypatch):
    calls=[]
    point=dict(lat=10.,lon=20.)
    reverse=dict(lat='10.0',lon='20.0',address=dict(city='Test City',country='Testland'))
    raw=dict(elements=[dict(type='way',id=1,nodes=[1,2],tags=dict(highway='residential',name='OFFLINE TEST'),geometry=[dict(lat=10,lon=20),dict(lat=10.001,lon=20)])])
    def request(url,config,**kwargs):
        calls.append((url,kwargs));return raw if kwargs.get('data') else reverse
    monkeypatch.setattr(geo,'request_json',request)
    first=geo.map_evidence(point,400,{},tmp_path)
    assert first==geo.map_evidence(point,400,{},tmp_path) and len(calls)==2
    assert set(calls[0][1]['params'])=={'lat','lon','format','addressdetails','zoom'}
    assert 'VIOOH' not in calls[1][1]['data']['data']
    reverse['lat']='11'
    with pytest.raises(ValueError,match='过远'):geo.map_evidence(point,200,{},tmp_path)


def test_short_model_source_alias_resolves_to_persisted_map_id():
    context=fixture_context()
    def create(**kwargs):
        supplied=json.loads(kwargs['messages'][1]['content'])
        assert supplied['map_features'][0]['id']=='F001'
        assert supplied['map_features'][0]['source_record_id']==context['evidence']['features'][0]['id']
        result=dict(environment_interpretation='Offline source alias test',audience_hypotheses=[dict(name='test'+str(i),rationale='offline hypothesis',source_ids=['F001']) for i in range(4)],uncertainties=['offline'])
        return SimpleNamespace(choices=[SimpleNamespace(finish_reason='stop',message=SimpleNamespace(content=json.dumps(result)))])
    client=SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    output=geo.interpret(context['frame'],context['evidence'],dict(LLM_MODEL_NAME='offline'),client)
    assert all(r['source_ids']==[context['evidence']['features'][0]['id']] for r in output['audience_hypotheses'])


def test_direct_map_context_keeps_evidence_without_claiming_model_inference():
    original=fixture_context()
    value=geo.verified_map_context(original['frame'],original['evidence'],'d'*32)
    assert value['status']=='map_verified'
    assert value['evidence']==original['evidence']
    assert [s['id'] for s in value['locality']['sources']]==['geo-map-evidence']
    assert not value['inference']['audience_hypotheses']
    assert geographic_network(value)==geographic_network(original)
