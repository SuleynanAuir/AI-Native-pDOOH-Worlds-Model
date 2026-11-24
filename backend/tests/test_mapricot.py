"""Meaningful offline contract tests; these fixtures are not live geographic evidence."""
import copy
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from app import create_app
from app.audience import mapricot_provider as mp,regions
from app.audience.geolocation import map_evidence
from app.audience.world import write_json

CONFIG=dict(LOCATION_LOOKUP_ENABLED=True,LOCATION_PROVIDER='mapricot',MAPRICOT_API_KEY='TEST_ONLY_NOT_A_REAL_KEY')


def fixture_lookup():
    return dict(address=dict(id='test-address',type='address',lat=10.,lon=20.,label='Offline Test Road',address=dict(country='Testland',locality='Test City',street='Test Road')),pois=[dict(id='test-poi',name='Offline Test Library',lat=10.0001,lon=20.,distance_m=11.1,source='offline')],address_granularity='address',address_distance_m=0.,queried_at='2026-01-01T00:00:00Z',radius_m=600,attribution=[dict(text='OFFLINE TEST ONLY',source='test',url='https://example.org')])


def inventory():
    return dict(id='a'*32,filename='offline.xlsx',sheet='FilteredFrames',frames=[dict(key='f'+str(i),screen_id='S'+str(i),coordinate=dict(lat=10.,lon=20.),city='Unverified Market',address='Original address',poi='Unverified original POI',venue='street',error='') for i in range(2)])


def test_sdk_uses_only_coordinates_and_cache_filters_out_of_range(monkeypatch,tmp_path):
    calls=[];address=fixture_lookup()['address'];near=fixture_lookup()['pois'][0]
    class SDK:
        def __init__(self,key,**kwargs):
            assert key==CONFIG['MAPRICOT_API_KEY'];assert 'base_url' not in kwargs
            self.geocoding=SimpleNamespace(reverse=self.reverse);self.places=SimpleNamespace(nearby=self.nearby)
        def reverse(self,*args,**kw):calls.append(('reverse',args,kw));return dict(results=[address],attribution=[])
        def nearby(self,*args,**kw):calls.append(('nearby',args,kw));return dict(results=[near,dict(near,id='far',lat=11),dict(near,id='bad',lat=float('nan'))],attribution=[])
    monkeypatch.setattr('mapricot.Mapricot',SDK)
    result=mp.lookup(dict(lat=10.,lon=20.),600,CONFIG,tmp_path)
    assert [p['id'] for p in result['pois']]==['test-poi']
    assert result==mp.lookup(dict(lat=10.,lon=20.),600,CONFIG,tmp_path)
    assert len(calls)==2 and calls[1][1]==(10.,20.) and calls[1][2]['limit']==20
    assert calls[0][2]['limit']==1
    with pytest.raises(ValueError,match='未启用'):mp.lookup(dict(lat=10,lon=20),600,dict(CONFIG,LOCATION_LOOKUP_ENABLED=False),tmp_path)


def test_style_never_returns_server_key_and_rewrites_source(monkeypatch):
    source={'sources':{'map':{'url':mp.BASE+'/tiles/v1/planet.json?key='+CONFIG['MAPRICOT_API_KEY']}},'glyphs':mp.BASE+'/tiles/v1/fonts/{fontstack}/{range}.pbf','debug':CONFIG['MAPRICOT_API_KEY']}
    monkeypatch.setattr(mp,'tile_bytes',lambda *args:json.dumps(source).encode())
    document=mp.map_document('style',CONFIG)
    assert document['sources']['map']['url']=='/api/world/mapricot/tilejson'
    assert CONFIG['MAPRICOT_API_KEY'] not in json.dumps(document)
    with pytest.raises(ValueError):mp.map_document('https://evil.invalid',CONFIG)


def test_provider_does_not_fall_back_to_unapproved_services(monkeypatch,tmp_path):
    def fail(*a,**kw):raise ValueError('Mapricot unavailable')
    monkeypatch.setattr(mp,'evidence',fail)
    import app.audience.geolocation as geo
    monkeypatch.setattr(geo,'request_json',lambda *a,**k:pytest.fail('No Nominatim or Overpass fallback'))
    with pytest.raises(ValueError,match='Mapricot unavailable'):map_evidence(dict(lat=10,lon=20),400,CONFIG,tmp_path)


def test_regions_deduplicate_coords_not_screens_and_preserve_original_poi(monkeypatch,tmp_path):
    calls=[]
    def lookup(*args):calls.append(args);return fixture_lookup()
    monkeypatch.setattr(mp,'lookup',lookup)
    inv=inventory();result=regions.build(inv,CONFIG,tmp_path,'b'*32)
    assert len(calls)==1 and result['total']==1 and result['completed']==1
    assert result['counts']=={'verified':2} and len(result['frames'])==2 and len(result['pois'])==1
    assert all(f['nearest_poi_id']=='test-poi' and f['city_conflict'] for f in result['frames'])
    assert all(f['poi']=='Unverified original POI' for f in result['frames'])
    assert result['groups'][0]['frame_keys']==['f0','f1']
    changed=copy.deepcopy(inv);changed['frames'][0]['coordinate']['lat']=9
    assert regions.fingerprint(inv)!=regions.fingerprint(changed)


def test_empty_pois_and_failed_lookup_are_not_invented(monkeypatch,tmp_path):
    v=fixture_lookup();v['pois']=[]
    monkeypatch.setattr(mp,'lookup',lambda *args:v)
    result=regions.build(inventory(),CONFIG,tmp_path,'b'*32)
    assert all(f['nearest_poi_id'] is None and not f['pois'] for f in result['frames'])
    def fail(*a):raise ValueError('HTTP 403')
    monkeypatch.setattr(mp,'lookup',fail)
    result=regions.build(inventory(),CONFIG,tmp_path,'c'*32)
    assert result['status']=='failed' and not result['groups'] and not result['pois']


def test_region_llm_rejects_cross_region_or_fabricated_sources(monkeypatch,tmp_path):
    monkeypatch.setattr(mp,'lookup',lambda *args:fixture_lookup())
    region=regions.build(inventory(),CONFIG,tmp_path,'b'*32);gid=region['groups'][0]['id']
    row=dict(id=gid,environment='Offline environment inference',simulation_implications='Offline assumptions',uncertainties=['No survey'],audiences=[dict(name='role'+str(i),behavior='hypothesis',periods='hypothesis',source_ids=['R1P1']) for i in range(4)])
    def create(**kw):
        supplied=json.loads(kw['messages'][1]['content']);assert supplied[0]['city']=='Test City'
        return SimpleNamespace(choices=[SimpleNamespace(finish_reason='stop',message=SimpleNamespace(content=json.dumps(dict(regions=[row]))))])
    client=SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    assert regions.analyze(region,dict(LLM_MODEL_NAME='offline'),client)['classification']=='scenario_hypotheses_not_population_statistics'
    row['audiences'][0]['source_ids']=['invented-facility']
    with pytest.raises(ValueError,match='跨区域'):regions.analyze(region,dict(LLM_MODEL_NAME='offline'),client)


def test_same_city_spatially_distant_screens_do_not_share_region():
    a=inventory()['frames'][0]|dict(status='verified',resolved_address=fixture_lookup()['address'],pois=[])
    b=copy.deepcopy(a);b['key']='distant';b['coordinate']['lat']+=.2
    groups=regions.region_groups([a,b]);assert len(groups)==2
    assert all('不是行政社区' in g['basis'] for g in groups)


def test_map_api_enabled_config_does_not_disclose_key(tmp_path,monkeypatch):
    app=create_app();app.config.update(TESTING=True,UPLOAD_FOLDER=str(tmp_path),**CONFIG)
    client=app.test_client();r=client.get('/api/world/location-config')
    assert r.json['data']['provider']=='mapricot' and r.json['data']['enabled']
    assert CONFIG['MAPRICOT_API_KEY'] not in r.get_data(as_text=True)
    assert client.get('/api/world/mapricot/invalid').status_code==400
    def forbidden(*a,**kw):pytest.fail('Disabled provider must not start requests')
    monkeypatch.setattr(regions,'build',forbidden);app.config['LOCATION_LOOKUP_ENABLED']=False
    assert client.post('/api/world/regions',json={}).status_code==400


def test_tile_projection_nodes_intersections_without_connecting_bridges(monkeypatch,tmp_path):
    import math
    x,y=mp.tile_xy(37.777738,-122.423367);x,y=math.floor(x),math.floor(y);n=2**15
    point=dict(lon=(x+.5)/n*360-180,lat=math.degrees(math.atan(math.sinh(math.pi*(1-2*(y+.5)/n)))))
    def road(coords,bridge=False):return dict(properties=dict(kind='minor_road',kind_detail='residential',name='OFFLINE TEST ROAD',is_bridge=bridge),geometry=dict(type='LineString',coordinates=coords))
    tile={'roads':dict(extent=4096,features=[road([[1850,2048],[2246,2048]]),road([[2048,1850],[2048,2246]]),road([[1850,1850],[2246,2246]],True)])}
    monkeypatch.setattr(mp,'cached',lambda *args:tile)
    features=mp.local_geometry(point,100,CONFIG,tmp_path)
    ground=[f for f in features if not f['tags'].get('bridge')];bridges=[f for f in features if f['tags'].get('bridge')]
    assert len(ground)==4 and len(bridges)==1
    from collections import Counter
    nodes=Counter(n for f in ground for n in f['nodes']);assert max(nodes.values())==4
    assert not set(nodes).intersection(n for f in bridges for n in f['nodes'])
    assert min(f['distance_m'] for f in ground)<.1
    assert all(abs(p['lat']-point['lat'])<.001 for f in features for p in f['geometry'])


def test_long_road_crossing_window_is_kept_without_inside_vertices(monkeypatch,tmp_path):
    import math
    x,y=map(math.floor,mp.tile_xy(37.777738,-122.423367));n=2**15
    point=dict(lon=(x+.5)/n*360-180,lat=math.degrees(math.atan(math.sinh(math.pi*(1-2*(y+.5)/n)))))
    road=dict(properties={'kind':'major_road','name':'TEST LONG ROAD'},geometry={'type':'LineString','coordinates':[[0,2048],[4096,2048]]})
    monkeypatch.setattr(mp,'cached',lambda *args:{'roads':{'extent':4096,'features':[road]}})
    features=mp.local_geometry(point,100,CONFIG,tmp_path)
    assert any(f['tags'].get('name')=='TEST LONG ROAD' for f in features)
    assert all(abs(g['lon']-point['lon'])<.002 for f in features for g in f['geometry'])
