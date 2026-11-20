import copy
from pathlib import Path
import pytest
from app import create_app
from app.audience import campaign_narratives as n
from app.audience.world import write_json,read_json


def fixture():
    profile=dict(preferences='优先耐用与实用',purchasing_power='预算偏紧的情景假设',needs='通勤与日用品',current_need='赶去上班',household='家庭情况未知',price_sensitivity='较高',life_stage='就业阶段')
    people=[dict(id=0,name='通勤者 01',group='commuter',audience_profile=profile,represented_population=100,local_context={}),dict(id=1,name='通勤者 02',group='commuter',audience_profile={**profile,'current_need':'有时间比较信息'},represented_population=200,local_context={})]
    groups=[dict(id='commuter',name='社区通勤者',profile=profile)]
    scores=dict(agents={str(i):dict(agent_id=i,interest=20+i*10,favorability=40+i*5,confidence='low',reason='当前需求与跑步广告关联有限',source_ids=['R1']) for i in range(2)},groups=[dict(id='commuter',interest=26.67,favorability=43.33)])
    evidence=dict(campaign=dict(title='NIKE RUNNING',message='Your pace'),sources=[dict(id='R1',kind='campaign',url='https://about.nike.com',title='Brand facts')],facts=[dict(statement='品牌宣称缓震舒适',source_ids=['R1'])],gaps=['没有价格信息'])
    base=dict(meta={'id':'a'*32,'title':'测试街区'},groups=groups)
    return base,people,dict(country='United States',city='San Francisco',community='Gough Street'),evidence,scores


def person_rows(people):
    rows=[dict(agent_id=a['id'],interpretation='此人的出行任务优先，广告的舒适诉求可能与日常通勤相关，但兴趣有限。',budget_reasoning='画像预算偏紧，广告未给价格，是否负担得起仍未知，可能先比较。',inner_thought='我现在要赶路，舒服是好事，但暂时没有买鞋计划。',possible_comment=f'我可能先看一下参数，再比较价格，人物{a["id"]}并不代表实际买家。',next_action='如果之后有换鞋需求，可能再查价格与试穿信息。',profile_fields=['preferences','purchasing_power','current_need'],source_ids=['local-context','R1']) for a in people]

    for row in rows:
        for key in n.PERSON_FIELDS[:5]:row[key]*=4
        row['decision_implications']='先验证通勤便利与舒适主张是否被理解，短文案避免占用过街注意力；如有安全候车位置可测试信息入口，价格未核实前不写优惠。此建议来自出行任务与耐用偏好，不能用模型分数直接扩大预算。'*2
        row['uncertainty']='预算偏紧只是合成画像，未记录收入、换鞋需求与真实停留；需核查可接受价格、阅读机会及舒适需求是否成立。广告官方宣称不等于人物实际体验。'*2
    return rows


def group_rows(groups):
    rows=[dict(group_id=g['id'],summary='社区通勤者以日常通行为主要任务，可能关注舒适与耐用，但这并不意味着愿意立即购买。预算约束与广告缺少价格信息会影响后续选择。',differences='组内人物的时间压力与当前需求不同，有人只愿意扫一眼，也有人可能稍后比较资料。',purchase_barriers='当前没有明确换鞋需求且价格未知，需要确认合脚程度与预算适配后才可能进一步考虑。',source_ids=['R1','local-context']) for g in groups]

    for row in rows:
        for key in n.GROUP_FIELDS[:3]:row[key]*=4
        for key in n.GROUP_FIELDS[3:]:row[key]='建议把通勤便利与耐用诉求作为待验证的信息方向，先核查路侧屏幕的可读距离与安全停留条件，再以相同场所和时段比较两种文案。观察广告理解与后续查资料行为，并通过实际访谈确认需求；模拟经过次数不是实际观看或购买，缺少成本与基线时不分配预算。'*3
    return rows


def test_profile_grounding_ids_references_and_missing_text_rejected():
    _,people,_,_,_=fixture();rows=person_rows(people)
    assert len(n.validate_people({'agents':rows},people,{'R1','local-context'}))==2
    for mutate in [lambda r:r.pop(),lambda r:r[1].update(agent_id=0),lambda r:r[0].update(possible_comment=''),lambda r:r[0].update(profile_fields=['preferences','current_need','needs']),lambda r:r[0].update(profile_fields=['preferences','purchasing_power','invented_income']),lambda r:r[0].update(source_ids=['other-city']),lambda r:r[1].update(possible_comment=r[0]['possible_comment'])]:
        bad=copy.deepcopy(rows);mutate(bad)
        with pytest.raises(ValueError):n.validate_people({'agents':bad},people,{'R1','local-context'})
    rows[0].update(interest=99,favorability=99,name='invented identity')
    validated=n.validate_people({'agents':rows},people,{'R1','local-context'})
    assert 'interest' not in validated[0] and 'name' not in validated[0]


def test_local_sources_not_applied_to_other_communities():
    *_,evidence,analysis=fixture()
    evidence['sources'] += [dict(id='R2',kind='local',country='United States',city='San Francisco',community_contains='stockton'),dict(id='R3',kind='local',country='United Kingdom',city='London')]
    evidence['facts'] += [dict(statement='另一区资料',source_ids=['R2']),dict(statement='另一城市资料',source_ids=['R3'])]
    sources,facts,allowed=n.scope_evidence(dict(country='United States',city='San Francisco',community='Gough Street'),evidence)
    assert allowed=={'R1','local-context'} and len(facts)==1 and len(sources)==1


def test_text_keeps_original_scores_profiles_and_reuses_checkpoints(tmp_path):
    base,people,locality,evidence,scores=fixture();before=copy.deepcopy(scores);calls=[]
    def model(config,prompt,payload,**kwargs):
        calls.append(payload)
        if 'agents' in payload:return {'agents':person_rows(people)}
        return {'groups':group_rows(base['groups'])}
    result=n.generate_scene(base,people,locality,evidence,scores,{'LLM_MODEL_NAME':'offline-fixture'},tmp_path,model=model)
    assert scores==before
    assert result['agents']['0']['interest']==20 and result['agents']['1']['favorability']==45
    assert result['agents']['0']['profile']==people[0]['audience_profile']
    assert result['groups'][0]['example_agent_ids']==[0,1]
    assert len(calls)==2
    assert set(calls[0]['agents'][0]['attitude'])=={'interest','favorability','confidence'}
    assert 'reason' not in calls[0]['agents'][0]['attitude']
    again=n.generate_scene(base,people,locality,evidence,scores,{'LLM_MODEL_NAME':'offline-fixture'},tmp_path,model=model)
    assert len(calls)==2 and again['agents']==result['agents']
    reused=n.generate_scene(base,people,locality,evidence,scores,{'LLM_MODEL_NAME':'offline-fixture'},tmp_path/'another',model=model,reuse=result)
    assert reused==result and len(calls)==2
    report=n.report_text([result])
    assert '不是真实消费者评价' in report and '可能评论（模拟）' in report and '预算偏紧' in report


def test_api_hides_incomplete_results_and_exports_bound_campaign(tmp_path,monkeypatch):
    app=create_app();app.config.update(TESTING=True,UPLOAD_FOLDER=str(tmp_path));client=app.test_client();identifier='b'*32;sid='a'*32
    d=tmp_path/'campaign_experiments'/identifier;d.mkdir(parents=True)
    state=dict(id=identifier,status='completed',spec={'scene_ids':[sid]});write_json(d/'state.json',state);before=(d/'state.json').read_bytes()
    url='/api/world/campaign-experiments/'+identifier+'/narratives'
    assert client.get(url).json['data']['status']=='not_started'
    assert client.get(url+'/scenes/'+sid).status_code==400
    assert client.get(url+'/scenes/'+'c'*32).status_code==400
    assert client.get(url+'/report.txt').status_code==400
    saved=[]
    monkeypatch.setattr(n,'start',lambda *args: saved.append(args) or {'status':'queued'})
    assert client.post(url,json={}).status_code==202 and saved[0][3]==identifier
    base,people,locality,evidence,scores=fixture()
    def model(config,prompt,payload,**kwargs):return {'agents':person_rows(people)} if 'agents' in payload else {'groups':group_rows(base['groups'])}
    data=n.generate_scene(base,people,locality,evidence,scores,{'LLM_MODEL_NAME':'offline'},tmp_path/'work',model=model)
    target=d/'narratives'/f'v{n.VERSION}';target.mkdir(parents=True);write_json(target/(sid+'.json'),data);write_json(target/'state.json',{'status':'completed'})
    assert client.get(url+'/scenes/'+sid).json['data']['agents']['0']['interest']==20
    download=client.get(url+'/report.txt')
    assert download.status_code==200 and 'attachment' in download.headers['Content-Disposition']
    assert '模拟表达' in download.data.decode('utf-8')
    brief=client.get(url+'/report.txt?scope=groups')
    assert brief.status_code==200 and 'audience-decision-brief.txt' in brief.headers['Content-Disposition']
    assert '创意与信息安排' in brief.data.decode() and '内心想法（模拟）：' not in brief.data.decode()
    assert client.get(url+'/report.txt?scope=invalid').status_code==400
    assert (d/'state.json').read_bytes()==before


def test_detailed_text_rejects_old_short_output_and_missing_decision_fields():
    base,people,*_=fixture()
    rows=person_rows(people)
    rows[0]['decision_implications']='需要更多研究'
    with pytest.raises(ValueError):n.validate_people({'agents':rows},people,{'R1','local-context'})
    rows=group_rows(base['groups']);rows[0].pop('validation_plan')
    with pytest.raises(ValueError):n.validate_groups({'groups':rows},base['groups'],{'R1','local-context'})


def test_hourly_evidence_uses_only_known_pedestrian_weights():
    base,people,*_=fixture()
    base['meta']['schedule']=[dict(round=1,time='08:00',period_label='上班高峰'),dict(round=2,time='09:00')]
    base['events']=[dict(round=1,actor_id='p-0-0',kind='pedestrian',count=100),dict(round=1,actor_id='p-1-0',kind='pedestrian',count=200),dict(round=2,actor_id='p-0-1',kind='pedestrian',count=100),dict(round=1,actor_id='v-0',kind='vehicle',count=500),dict(round=1,actor_id='p-999-0',kind='pedestrian',count=800)]
    result=n.exposure_context(base,people)['commuter']
    assert [h['weighted_opportunities'] for h in result['hours']]==[300,100]
    assert '非实测' in result['label']


def test_short_batch_is_repaired_with_person_specific_feedback(tmp_path):
    base,people,locality,evidence,scores=fixture();prompts=[]
    def model(config,prompt,payload,**kwargs):
        if 'agents' not in payload:return {'groups':group_rows(base['groups'])}
        prompts.append(prompt);rows=person_rows(people)
        if len(prompts)==1:
            for key in n.PERSON_FIELDS:rows[1][key]='这段只有笼统解释，没有结合当时需求和预算形成完整的判断，更没有后续验证条件。'
        return {'agents':rows}
    result=n.generate_scene(base,people,locality,evidence,scores,{'LLM_MODEL_NAME':'offline'},tmp_path,model=model)
    assert len(prompts)==2 and '人物 1' in prompts[1] and '至少600字' in prompts[1]
    assert len(result['agents'])==2


def test_person_and_group_batches_cover_every_identity(tmp_path):
    base,seed,locality,evidence,scores=fixture();people=[];groups=[];analysis={'agents':{},'groups':[]};calls=[]
    for i in range(3):
        group={**base['groups'][0],'id':f'g{i}','name':f'群体{i}'};groups.append(group)
        for j in range(2):
            aid=i*2+j;people.append({**seed[j],'id':aid,'group':group['id']})
            analysis['agents'][str(aid)]={**scores['agents'][str(j)],'agent_id':aid}
        analysis['groups'].append({**scores['groups'][0],'id':group['id']})
    base={**base,'groups':groups}
    def model(config,prompt,payload,**kwargs):
        if 'agents' in payload:
            ids=[a['agent_id'] for a in payload['agents']];calls.append(('people',ids))
            return {'agents':person_rows([p for p in people if p['id'] in ids])}
        ids=[g['id'] for g in payload['groups']];calls.append(('groups',ids))
        return {'groups':group_rows([g for g in groups if g['id'] in ids])}
    result=n.generate_scene(base,people,locality,evidence,analysis,{'LLM_MODEL_NAME':'offline'},tmp_path,model=model)
    assert [len(ids) for kind,ids in calls if kind=='people']==[2,2,2]
    assert [len(ids) for kind,ids in calls if kind=='groups']==[2,1]
    assert len(result['agents'])==6 and len(result['groups'])==3


def test_hourly_evidence_changes_invalidate_reuse_but_vehicle_only_changes_do_not():
    base,people,locality,evidence,scores=fixture();sources,facts,_=n.scope_evidence(locality,evidence)
    base['meta']['schedule']=[dict(round=1,time='08:00')];base['events']=[]
    def fingerprint():return n.narrative_fingerprint(base,people,evidence,scores,{'LLM_MODEL_NAME':'offline'},sources,facts)
    initial=fingerprint()
    base['events'].append(dict(round=1,actor_id='v-1',kind='vehicle',count=200))
    assert fingerprint()==initial
    base['events'].append(dict(round=1,actor_id='p-0-0',kind='pedestrian',count=100))
    assert fingerprint()!=initial


def test_reader_terminology_does_not_expose_model_field_names():
    assert n.reader_text('exposure_context 是模拟加权经过机会')=='模拟时段分布 是模拟加权经过机会'
