from copy import deepcopy
from types import SimpleNamespace
import json
import pytest
from app import create_app
from app.audience.cohorts import DEFAULT_SEGMENTS, validate_segments, representatives
from app.audience.day_cycle import attendance, schedule, validate_day_cycle
from app.audience.locality import validate_locality, locality_hash, scoped_sources, generate_template, LOCAL_FIELDS
from app.audience.world import scene, write_json


def locality():
    return dict(country='United States of America',city='Emeryville',community='城市接驳社区',venue_type='station',venue_name='合成候车区域',languages='',cultural_notes='',community_notes='',sources=[dict(id='local-doc',title='当地交通资料',text='社区居民和工作者使用交通接驳。',country='USA',city='Emeryville',community='',url='https://example.org/local',kind='document'),dict(id='wrong-doc',title='其他城市资料',text='不得带入本地推演。',country='France',city='Paris',community='',url='',kind='assumption')])


def local_segments():
    segments=deepcopy(DEFAULT_SEGMENTS[:4])
    for i,s in enumerate(segments):
        s.update(id=f'local-{i}',local_context={k:'当地场所的合成角色，需资料校正' for k in LOCAL_FIELDS},local_rationale='根据本地接驳资料推演候车任务，人数和家庭情况仅为假设',source_ids=['local-doc'],activity_factors=dict(morning=.5,evening=1.2,night=.8,daytime=1,quiet=0))
    return segments


def fake_client(payload, capture=None):
    def create(**kwargs):
        if capture is not None:capture.update(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(finish_reason='stop',message=SimpleNamespace(content=json.dumps(payload,ensure_ascii=False)))])
    return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))


def test_scope_country_aliases_and_community_boundaries():
    value=validate_locality(locality());used,ignored=scoped_sources(value)
    assert [s['id'] for s in used]==['local-doc']
    assert ignored[0]['id']=='wrong-doc'
    value['sources'][0]['community']='另一个社区'
    assert not scoped_sources(value)[0]
    value['sources'][0]['community']='';value['sources'][0]['city']=''
    assert '未标明' in scoped_sources(value)[1][0]['reason']


@pytest.mark.parametrize('field,value',[('country',''),('city',True),('community',''),('venue_type','invalid'),('sources',None)])
def test_invalid_locality(field,value):
    loc=locality();loc[field]=value
    with pytest.raises(ValueError):validate_locality(loc)


def test_source_links_duplicate_ids_and_nonfinite_factors():
    loc=locality();loc['sources'][0]['url']='javascript:alert(1)'
    with pytest.raises(ValueError):validate_locality(loc)
    loc=locality();loc['sources'][1]['id']='local-doc'
    with pytest.raises(ValueError):validate_locality(loc)
    s=local_segments();s[0]['activity_factors']['quiet']=float('nan')
    with pytest.raises(ValueError):validate_segments(s)


def test_generation_passes_only_scoped_sources_and_preserves_local_fields():
    capture={};payload=dict(summary='根据社区接驳任务构建画像',uncertainties=['人数缺少调查'],segments=local_segments())
    result=generate_template(locality(),4,dict(LLM_MODEL_NAME='test'),fake_client(payload,capture))
    supplied=json.loads(capture['messages'][1]['content'])
    assert [d['id'] for d in supplied['documents']]==['local-doc']
    assert 'wrong-doc' not in capture['messages'][1]['content']
    assert result['segments'][0]['local_context']
    assert result['context_hash']==locality_hash(locality())
    assert result['segments'][0]['share_basis']=='scenario_assumption'
    assert result['ignored_sources'][0]['id']=='wrong-doc'
    agents,groups=representatives(100,30000,segments=result['segments'])
    assert sum(a['represented_population'] for a in agents)==30000
    assert all(a['local_context'] and a['activity_factors'] and a['source_ids'] for a in agents)


def test_no_documents_is_explicit_assumption_and_bad_citations_fail():
    loc=locality();loc['sources']=[]
    payload=dict(summary='无地区资料的场景推演',uncertainties=[],segments=local_segments())
    for s in payload['segments']:s['source_ids']=['context']
    result=generate_template(loc,4,dict(LLM_MODEL_NAME='test'),fake_client(payload))
    assert result['grounding']=='scenario_only' and result['uncertainties']
    payload['segments'][0]['source_ids']=['fabricated']
    with pytest.raises(ValueError):generate_template(loc,4,dict(LLM_MODEL_NAME='test'),fake_client(payload))


def test_local_activity_is_not_based_on_legacy_id_and_venue_changes_screens():
    agents,_=representatives(100,10000,segments=local_segments())
    slots=schedule(validate_day_cycle({}));a=agents[0]
    assert attendance(a,slots[0],42)['present'] is False
    assert attendance(a,slots[8],42)['relative_activity_factor']==.5
    assert attendance(a,slots[8],42)==attendance({**a,'group':'professional'},slots[8],42)
    loc=locality();station=scene(100,segments=local_segments(),day_cycle={},locality=loc)
    loc['venue_type']='airport';airport=scene(100,segments=local_segments(),day_cycle={},locality=loc)
    assert station['screens'][0]['name']!=airport['screens'][0]['name']
    assert all(s['visibility'] is None for s in airport['screens'])
    assert airport['schema_version']==5


def test_server_binds_template_to_country_community_venue_and_sources(tmp_path):
    app=create_app();app.config.update(TESTING=True,UPLOAD_FOLDER=str(tmp_path));c=app.test_client()
    loc=validate_locality(locality());tid='b'*32
    path=tmp_path/'audience_templates';path.mkdir()
    saved=dict(id=tid,locality=loc,context_hash=locality_hash(loc),segments=local_segments(),used_source_ids=['context','local-doc'],summary='test',uncertainties=[],ignored_sources=[],grounding='source_informed_inference')
    write_json(path/(tid+'.json'),saved)
    data=dict(agent_count=100,total_population=30000,day_cycle={},locality=loc,template_id=tid,segments=local_segments())
    response=c.post('/api/world/preview',json=data)
    assert response.status_code==200
    assert response.json['data']['agents'][0]['local_context']
    for key,value in [('country','France'),('city','Paris'),('community','其他社区'),('venue_type','supermarket'),('community_notes','新增资料')]:
        changed=deepcopy(data);changed['locality'][key]=value
        assert c.post('/api/world/runs',json=changed).status_code==400
    changed=deepcopy(data);changed['segments'][0]['source_ids']=['wrong-doc']
    assert c.post('/api/world/preview',json=changed).status_code==400
    del data['template_id']
    assert c.post('/api/world/preview',json=data).status_code==400
    assert not list(tmp_path.glob('worlds/*/state.json'))


def test_model_failure_does_not_pretend_to_generate_and_inventory_retains_raw_values(tmp_path,monkeypatch):
    app=create_app();app.config.update(TESTING=True,UPLOAD_FOLDER=str(tmp_path));c=app.test_client()
    def fail(*args):raise RuntimeError('provider-secret-body')
    monkeypatch.setattr('app.audience.world_routes.generate_template',fail)
    response=c.post('/api/world/local-audiences',json=dict(locality=locality(),group_count=4))
    assert response.status_code==502 and 'provider-secret-body' not in response.text
    assert not list(tmp_path.glob('audience_templates/*.json'))
    response=c.post('/api/world/location-inventory',json={})
    assert response.status_code==200 and len(response.json['data']['candidates'])==149
    row=response.json['data']['candidates'][0]
    assert row['city']=='Sacramento et al' and 'San Francisco' in row['poi']


def test_wrong_group_count_gets_one_bounded_model_repair():
    good=dict(summary='Offline repair test',uncertainties=['No real demographic evidence'],segments=local_segments())
    bad=deepcopy(good);bad['segments']=bad['segments'][:3];calls=[]
    def create(**kwargs):
        calls.append(deepcopy(kwargs))
        payload=bad if len(calls)==1 else good
        return SimpleNamespace(choices=[SimpleNamespace(finish_reason='stop',message=SimpleNamespace(content=json.dumps(payload)))])
    client=SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    result=generate_template(locality(),4,dict(LLM_MODEL_NAME='offline'),client)
    assert len(result['segments'])==4 and len(calls)==2
    assert '恰好 4 项' in calls[1]['messages'][-1]['content']
    assert len(bad['segments'])==3, 'Code must not duplicate roles to fill the requested count'
    calls.clear()
    def always_wrong(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(finish_reason='stop',message=SimpleNamespace(content=json.dumps(bad)))])
    client.chat.completions.create=always_wrong
    with pytest.raises(ValueError,match='一次格式修正'):generate_template(locality(),4,dict(LLM_MODEL_NAME='offline'),client)
    assert len(calls)==2
