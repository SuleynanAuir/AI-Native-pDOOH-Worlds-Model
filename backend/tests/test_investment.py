import copy
from decimal import Decimal
from io import BytesIO
from pathlib import Path
import json
import pytest

from app import create_app
from app.audience.investment import summarize,settings,returns,report,attach_plan,campaign_evidence
from app.audience.planning import ingest,plan,export_plan
from app.audience.workbook import read_workbook,write_workbook

SAMPLE=Path(__file__).resolve().parents[2]/'data/test.xlsx'


def base(sid='s'):
    return dict(meta=dict(id='a'*32,title='test',rounds=24,schedule=[dict(round=1,day=1,time='00:00')]),
        screens=[dict(id=sid)],attitudes=dict(agents={'0':dict(interest=0,favorability=80),'1':dict(interest=100,favorability=None)}),
        events=[dict(screen_id=sid,count=10,kind='pedestrian',actor_id='p-0-trip',round=1),
            dict(screen_id=sid,count=20,kind='pedestrian',actor_id='p-1-trip',round=1),
            dict(screen_id=sid,count=10,kind='pedestrian',actor_id='p-0-again',round=1),
            dict(screen_id=sid,count=60,kind='vehicle',actor_id='v-1',round=1)])


def test_dimension_denominators_zero_unknown_and_repeated_opportunities():
    r=summarize(base())['s']
    assert r['total']==100 and r['interest']==50 and r['favorability']==80
    assert r['interest_coverage']==.4 and r['favorability_coverage']==.2
    assert r['joint_rated']==20 and r['joint_high']==0
    assert r['high_interest']==20 and r['representatives']==2
    assert r['vehicle']==60


@pytest.fixture
def inventory(): return ingest(SAMPLE.read_bytes(),'test.xlsx','FilteredFrames')


def prepare(inventory,**updates):
    options=dict(budget=10000,currency='USD',days=28,start_date='2026-12-01')
    options.update(updates)
    sid=inventory['frames'][0]['screen_id']
    evidence=dict(campaign_id='b'*32,campaign={'title':'Test creative'},fingerprint='fixture',screens=summarize(base(sid)))
    result=plan(inventory,options)
    result['investment']=report(result,evidence,options)
    attach_plan(result)
    return result


def test_entire_filtered_sheet_and_exact_id_unknowns(inventory):
    r=prepare(inventory); d=r['investment']
    assert len(d['rows'])==144 and inventory['source_sheet']=='FilteredFrames'
    assert d['coverage']['direct']==1
    assert len([row for row in d['rows'] if row['dimensions']['interest'] is None])==143
    assert all(row['importance_low']<=row['importance']<=row['importance_high'] for row in d['rows'])
    assert d['returns']['base'] is None
    assert all(row['return_at_full_sot']['base'] is None for row in d['rows'])
    direct=next(row for row in d['rows'] if row['sim'])
    assert direct['dimensions']['interest']==50


@pytest.mark.parametrize('budget',[.01,100,10000,10000000])
def test_budget_caps_steps_and_unknown_exploration(inventory,budget):
    r=prepare(inventory,budget=budget,sot_step=.07,max_sot=.63,dsp_fee=.15,investment={'max_screen_share':.13,'exploration_share':.2})
    rows=r['investment']['rows']; a=r['investment']['allocation']
    assert sum(Decimal(str(x['recommended_amount'])) for x in rows)==Decimal(str(a['total']))
    assert a['total']<=budget and a['exploration']<=budget*.2
    assert a['remaining']==pytest.approx(budget-a['total'])
    for row in rows:
        assert row['recommended_amount']<=budget*.13
        assert 0<=row['recommended_sot']<=.63
        assert Decimal(str(row['recommended_sot']))%Decimal('.07')==0
    assert sum(x['total'] for x in r['plans'][-1]['items'])==pytest.approx(a['total'])


def test_exploration_zero_and_coordinate_conflict(inventory):
    sid=inventory['frames'][0]['screen_id']; b=base(sid); b['screens'][0]['coordinate']=dict(lat=0,lon=0)
    result=plan(inventory,dict(budget=10000,currency='USD'))
    evidence=dict(campaign_id='b'*32,campaign={},fingerprint='test',screens=summarize(b))
    d=report(result,evidence,dict(investment=dict(exploration_share=0)))
    assert d['coverage']['direct']==0 and d['allocation']['total']==0
    assert any('坐标' in w for w in next(r for r in d['rows'] if r['screen_id']==sid)['warnings'])


def test_roi_equations_and_zero_rate_are_not_missing():
    cfg=settings({'investment':{'roi':dict(order_value=100,margin=.4,incrementality=.5,rates=dict(low=0,base=1,high=2))}})['roi']
    r=returns(10000,100,cfg)
    assert r['low']['roi']==-1 and r['base']['orders']==5
    assert r['base']['revenue']==500 and r['base']['contribution']==200
    assert r['base']['roi']==1 and r['base']['roas']==5
    assert r['break_even_per_thousand']==.5
    cfg['overrides']['s']=dict(low=0,base=2,high=3)
    assert returns(10000,100,cfg,'s')['base']['roi']==3
    cfg['margin']=0
    assert returns(10000,100,cfg)['break_even_per_thousand'] is None
    cfg['incrementality']=None
    assert returns(10000,100,cfg)['base'] is None


def test_profit_objective_does_not_spend_when_no_profitable_or_missing_evidence(inventory):
    roi=dict(order_value=10,margin=.1,incrementality=.1,rates=dict(low=0,base=.001,high=.002))
    for value in ({},roi):
        r=prepare(inventory,investment=dict(objective='profit',roi=value))
        assert r['investment']['allocation']['total']==0
        assert all(r['recommended_amount']==0 for r in r['investment']['rows'])


def test_advertising_weights_change_selection_without_changing_conversion(inventory):
    inventory=copy.deepcopy(inventory);inventory['frames']=inventory['frames'][:2]
    ids=[f['screen_id'] for f in inventory['frames']]
    for f in inventory['frames']:
        f['fields'].update(IMPRESSIONS=100000,FLOORCPM=10)
    screens={}
    for sid,favor,interest in zip(ids,[90,10],[10,90]):
        b=base(sid)
        for a in b['attitudes']['agents'].values():a.update(interest=interest,favorability=favor)
        screens.update(summarize(b))
    for dimension,expected in [('favorability',ids[0]),('interest',ids[1])]:
        w={k:0 for k in ('exposure','favorability','interest','visibility','location','market','cost')};w[dimension]=1
        opts=dict(budget=100,currency='USD',days=30,investment=dict(weights=w,max_screen_share=1,exploration_share=0))
        r=report(plan(inventory,opts),dict(campaign_id='test',campaign={},fingerprint='test',screens=screens),opts)
        chosen=[row for row in r['rows'] if row['recommended_amount']]
        assert len(chosen)==1 and chosen[0]['screen_id']==expected
        assert chosen[0]['returns']['base'] is None


@pytest.mark.parametrize('config',[dict(weights={}),dict(weights={k:0 for k in ('exposure','favorability','interest','visibility','location','market','cost')}),dict(max_screen_share=0),dict(exploration_share=2),dict(roi={'margin':float('nan')}),dict(roi={'rates':dict(low=2,base=1,high=3)}),dict(roi={'overrides':[]}),dict(objective='made-up')])
def test_invalid_assumptions(config):
    with pytest.raises(ValueError): settings({'investment':config})


def test_filtered_only_import_and_export_contract(inventory):
    raw=write_workbook([('FilteredFrames',inventory['headers'],[[f['original'].get(k) for k in inventory['headers']] for f in inventory['frames']])])
    assert len(ingest(raw,'filtered.xlsx')['frames'])==144
    r=prepare(inventory,investment=dict(roi=dict(order_value=100,margin=.5,incrementality=.5,rates=dict(low=.2,base=.5,high=1))))
    sheets=read_workbook(export_plan(inventory,r,'investment'))
    assert len(sheets['Investment Ranking'])==145
    assert len(sheets['Return Scenarios'])==433
    assert sheets['Proposal'][0][0]=='Date'
    assert sum(row[sheets['Proposal'][0].index('Total investment')] for row in sheets['Proposal'][1:])==pytest.approx(r['investment']['allocation']['total'])
    for row in sheets['Return Scenarios'][1:]:
        if row[3]>0:
            assert row[8]==pytest.approx(row[2]/1000*row[4]*row[5])
            assert row[12]==pytest.approx((row[8]*row[6]*row[7]-row[3])/row[3])


def test_api_binds_campaign_evidence_server_side_and_all_inventory(tmp_path):
    app=create_app();app.config.update(TESTING=True,UPLOAD_FOLDER=str(tmp_path));client=app.test_client()
    p=client.post('/api/planning/import',data={'source_sheet':'FilteredFrames','workbook':(BytesIO(SAMPLE.read_bytes()),'test.xlsx')}).json['data']
    assert len(p['frames'])==144
    cid='b'*32;sid='a'*32;path=tmp_path/'campaign_experiments'/cid
    (path/'scenes'/sid).mkdir(parents=True)
    (path/'state.json').write_text(json.dumps(dict(id=cid,status='completed',spec=dict(scene_ids=[sid],campaign=dict(title='Test')))))
    (path/'scenes'/sid/'base.json').write_text(json.dumps(base(p['frames'][0]['screen_id'])))
    assert client.get('/api/planning/campaigns').json['data'][0]['id']==cid
    opts=dict(budget=10000,currency='USD',campaign_id=cid,investment={'fake_interest':100})
    r=client.post(f"/api/planning/{p['id']}/plan",json=opts)
    assert r.status_code==200 and r.json['data']['investment']['coverage']['direct']==1
    assert next(row for row in r.json['data']['investment']['rows'] if row['sim'])['sim']['interest']==50
    assert client.get(f"/api/planning/{p['id']}/export?strategy=investment").status_code==200
    opts['campaign_id']='../escape'
    assert client.post(f"/api/planning/{p['id']}/plan",json=opts).status_code==400
    state=json.loads((path/'state.json').read_text());state['status']='running';(path/'state.json').write_text(json.dumps(state))
    with pytest.raises(ValueError,match='完成'):campaign_evidence(tmp_path,cid)


def test_coverage_only_publishes_completed_same_campaign_snapshots(tmp_path):
    from app.audience.coverage import supplement
    from app.audience import store
    from app.audience.world import write_json
    project=store.create(tmp_path,{'frames':[]});pid=project['id'];cid='b'*32
    (tmp_path/'campaign_experiments'/cid).mkdir(parents=True)
    write_json(tmp_path/'campaign_experiments'/cid/'state.json',{'status':'completed'})
    p=tmp_path/'planning'/pid/('coverage-'+cid);(p/'scenes'/('a'*32)).mkdir(parents=True)
    write_json(p/'scenes'/('a'*32)/'base.json',base())
    state={'fingerprint':'f','items':{'s':{'status':'running','scene_id':'a'*32}}}
    write_json(p/'state.json',state)
    evidence={'fingerprint':'f','screens':{}}
    supplement(tmp_path,pid,cid,evidence);assert evidence['screens']=={}
    state['items']['s']['status']='completed';write_json(p/'state.json',state)
    supplement(tmp_path,pid,cid,evidence,90);assert evidence['screens']['s']['high_favorability']==0
    other={'fingerprint':'changed','screens':{}};supplement(tmp_path,pid,cid,other);assert other['screens']=={}
