"""Real-workbook regression, budget invariants and evidence/API contracts."""
import copy
import base64
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
import zipfile
import xml.etree.ElementTree as ET

import pytest
from app import create_app
from app.audience.planning import ingest, plan, clean, export_plan, PROPOSAL_HEADERS
from app.audience.workbook import read_workbook, write_workbook
from app.audience.analysis import validate_response, analyze_frame, public_image_url

SAMPLE=Path(__file__).resolve().parents[2]/'data/test.xlsx'

@pytest.fixture
def project(): return ingest(SAMPLE.read_bytes(),'data/test.xlsx')

def opts(**kw): return dict(budget=50000,currency='USD',days=28,start_date='2026-12-01',**kw)

def test_actual_inventory_contract_and_source_preservation(project):
    assert len(project['frames'])==149
    result=plan(project,opts())
    assert result['summary']==dict(total=149,eligible=144,rejected=5)
    for frame,source in zip(result['frames'],project['frames']):
        assert frame['original']==source['original']
        assert 'CLOEST_POI' in frame['original']
        assert frame['scores']['visibility']==50
        assert frame['evidence']['visibility']['type']=='assumption'
    assert all(p['total']<=50000 for p in result['plans'])
    assert len({p['strategy'] for p in result['plans']})==5


def test_header_semantics_alias_and_formula_text():
    headers=['Screen ID','Country','Latitude','Longitude','Impressions','CPM','Currency','VIOOHSELECTOPTIN','CLOEST_POI','Extra']
    raw=write_workbook([('UnfilteredFrames',headers,[['id','USA',30,-120,1000,10,'USD','Yes','a','=1+2']])])
    p=ingest(raw,'semantic.xlsx')
    assert p['frames'][0]['fields']['CLOSEST_POI']=='a'
    assert p['frames'][0]['original']['Extra']=='=1+2'
    assert plan(p,opts())['summary']['eligible']==1


def test_duplicate_missing_anomaly_and_region_filter(project):
    p=copy.deepcopy(project);p['frames']=p['frames'][:3]
    p['frames'][1]['screen_id']=p['frames'][0]['screen_id']
    p['frames'][2]['fields']['LATITUDE']=100
    frames=clean(p,{})
    assert not any(f['eligible'] for f in frames)
    assert '重复' in frames[0]['reasons'][0]
    assert not any(f['eligible'] for f in clean(project,{'filters':{'country':'GBR'}}))
    assert not any(f['eligible'] for f in clean(project,{'filters':{'bounds':[0,0,10,10]}}))


def test_score_p_never_drives_score(project):
    r=plan(project,opts())
    for frame in project['frames']: frame['fields']['SCORE_P']=999999
    changed=plan(project,opts())
    assert [x['total_score'] for x in r['frames']]==[x['total_score'] for x in changed['frames']]


@pytest.mark.parametrize('budget',[.01,1,100,1234.56,50000,10000000])
def test_budget_conservation_and_sot_bounds(project,budget):
    o=opts();o.update(budget=budget,dsp_fee=.15,cpm_markup=.2,sot_step=.07,max_sot=.6,currency='GBP',fx={'USD':1,'GBP':1.23},fx_source='test fixture',fx_date='2026-11-19')
    result=plan(project,o)
    for scenario in result['plans']:
        assert Decimal(str(scenario['total']))<=Decimal(str(budget))
        assert sum(Decimal(str(i['total'])) for i in scenario['items'])==Decimal(str(scenario['total']))
        for i in scenario['items']:
            assert 0<i['sot']<=.6
            assert Decimal(str(i['sot']))%Decimal('.07')==0
            assert i['rounding_reserve']>=0
            assert i['total']==pytest.approx(i['media_budget']+i['dsp_cost']+i['rounding_reserve'])
            assert i['dsp_cost']==pytest.approx(i['media_budget']*.15)
    assert not set(result['plans'][-1]['excluded_ids']) & {i['screen_id'] for i in result['plans'][-1]['items']}


def test_mixed_currencies_missing_fx_excludes_and_valid_fx_converts(project):
    p=copy.deepcopy(project);p['frames']=p['frames'][:1];p['frames'][0]['fields']['MEDIAOWNERCURRENCY']='EUR'
    assert plan(p,opts())['summary']['eligible']==0
    o=opts(fx={'EUR':1.2},fx_date='2026-11-19',fx_source='test')
    r=plan(p,o);assert r['frames'][0]['cpm_budget']==pytest.approx(12)
    with pytest.raises(ValueError):plan(p,opts(fx={'EUR':1.2}))


def test_budget_only_and_export_formulas(project):
    result=plan(project,dict(budget=50000,currency='USD'))
    assert result['finance']['budget_only']
    raw=export_plan(project,result,'balanced'); sheets=read_workbook(raw)
    assert {'FilteredFrames','Screen Scorecard','Proposal','PICS','Audit','POI'}<=sheets.keys()
    headers=sheets['Proposal'][0]
    assert headers[:len(PROPOSAL_HEADERS)]==PROPOSAL_HEADERS
    for row in sheets['Proposal'][1:]:
        assert row[headers.index('Impression deliverable')] is None
        assert row[headers.index('Estimated impressions')]>0
    total=sum(row[headers.index('Total investment')] for row in sheets['Proposal'][1:])
    assert total==pytest.approx(result['plans'][0]['total'])
    with zipfile.ZipFile(BytesIO(raw)) as z:
        xml=z.read('xl/worksheets/sheet3.xml')
        assert b'<f>' in xml and b'Rounding reserve' in xml


@pytest.mark.parametrize('key,value',[('budget',float('nan')),('budget',-1),('days',1.5),('dsp_fee',-1),('max_sot',1.1),('weights',{}),('filters',[]),('fx',[]),('sot_step',0),('start_date','bad')])
def test_invalid_options(project,key,value):
    o=opts();o[key]=value
    with pytest.raises(ValueError):plan(project,o)


def model_json():
    return dict(observations=[dict(statement='roadside screen',source='inventory',kind='fact')],scores={'visibility':dict(score=80,reason='clear view',source_ids=['image:photo.jpg']),'market':dict(score=70,reason='regional report',source_ids=['document:report.txt'])},audiences=[dict(name='commuters',passing='walking',staying='short pause possible',reaction='glance if visible',basis='hypothesis',confidence='low',source_ids=['inventory'])],uncertainties=['uncalibrated'],viewing_distance=dict(meters_min=None,meters_max=None,reason='no scale'))


def test_model_evidence_gates_and_nonexistent_citations():
    value=model_json()
    r=validate_response(value,['inventory'],False,False)
    assert r['scores']=={}
    with pytest.raises(ValueError):validate_response(value,['inventory'],True,True)
    r=validate_response(value,['inventory','image:photo.jpg','document:report.txt'],True,True)
    assert r['scores']['visibility']['score']==80


def test_multimodal_request_includes_image_and_context(project,tmp_path):
    import json
    raw=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aGa0AAAAASUVORK5CYII=')
    (tmp_path/'photo.image').write_bytes(raw)
    sid=project['frames'][0]['screen_id']
    project['photos'][sid]=dict(file='photo.image',source='photo.jpg')
    project['documents']=[dict(name='report.txt',text='Regional research')]
    calls=[]
    def create(**kw):
        calls.append(kw)
        return SimpleNamespace(choices=[SimpleNamespace(finish_reason='stop',message=SimpleNamespace(content=json.dumps(model_json())))])
    fake=SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    result=analyze_frame(project,project['frames'][0],'visibility focus',tmp_path,{'LLM_MODEL_NAME':'test'},fake)
    assert calls[0]['messages'][1]['content'][1]['type']=='image_url'
    assert 'Regional research' in calls[0]['messages'][1]['content'][0]['text']
    assert result['calibration']=='uncalibrated inference'


@pytest.mark.parametrize('url',['http://example.com/a.png','https://127.0.0.1/a','https://localhost/a','https://my.feishu.cn/drive/folder/abc','https://placehold.co/600x400'])
def test_unsafe_or_non_photo_urls(url):
    with pytest.raises(ValueError):public_image_url(url)


@pytest.fixture
def client(tmp_path):
    app=create_app();app.config.update(TESTING=True,UPLOAD_FOLDER=str(tmp_path))
    return app.test_client()


def test_api_import_plan_export_and_invalidated_evidence(client):
    r=client.post('/api/planning/import',data={'workbook':(BytesIO(SAMPLE.read_bytes()),'test.xlsx')})
    assert r.status_code==200
    pid=r.json['data']['id']
    assert client.post(f'/api/planning/{pid}/plan',json=opts()).status_code==200
    r=client.get(f'/api/planning/{pid}/export?strategy=balanced')
    assert r.status_code==200 and r.data[:2]==b'PK'
    assert client.post(f'/api/planning/{pid}/documents',data={'documents':(BytesIO('区域研究'.encode()),'region.txt')}).status_code==200
    assert client.get(f'/api/planning/{pid}/export').status_code==400
    assert client.post(f'/api/planning/{pid}/plan',json={'budget':-1}).status_code==400
    assert client.post(f'/api/planning/{pid}/plan',json=[]).status_code==400


def test_api_photo_association_and_unmatched_errors(client):
    r=client.post('/api/planning/sample');p=r.json['data'];pid=p['id'];sid=p['frames'][0]['screen_id']
    raw=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aGa0AAAAASUVORK5CYII=')
    r=client.post(f'/api/planning/{pid}/photos',data={'photos':(BytesIO(raw),sid+'.png')})
    assert r.status_code==200 and sid in r.json['data']['photos']
    assert client.post(f'/api/planning/{pid}/photos',data={'photos':(BytesIO(raw),'unknown.png')}).status_code==400
    assert client.post(f'/api/planning/{pid}/analyze',json={'screen_ids':[]}).status_code==400


def test_uploaded_picture_embedded_and_corrupt_rejected(client):
    p=client.post('/api/planning/sample').json['data'];pid=p['id']
    result=client.post(f'/api/planning/{pid}/plan',json=opts()).json['data']
    sid=result['plans'][0]['items'][0]['screen_id']
    assert client.post(f'/api/planning/{pid}/photos',data={'screen_id':sid,'photos':(BytesIO(b'\x89PNG\r\n\x1a\nnot-image'),'bad.png')}).status_code==400
    raw=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aGa0AAAAASUVORK5CYII=')
    assert client.post(f'/api/planning/{pid}/photos',data={'screen_id':sid,'photos':(BytesIO(raw),'scene.png')}).status_code==200
    assert client.post(f'/api/planning/{pid}/plan',json=opts()).status_code==200
    raw=client.get(f'/api/planning/{pid}/export').data
    with zipfile.ZipFile(BytesIO(raw)) as z:
        assert any(n.startswith('xl/media/') for n in z.namelist())
        assert b'<drawing ' in z.read('xl/worksheets/sheet4.xml')


def test_dedicated_vision_model_and_disabled_guard(project,tmp_path):
    import json
    sid=project['frames'][0]['screen_id']
    project['photos'][sid]=dict(url='https://example.com/photo.jpg',source='photo.jpg')
    project['documents']=[dict(name='report.txt',text='Synthetic study')]
    calls=[]
    def create(**kw):
        calls.append(kw)
        return SimpleNamespace(choices=[SimpleNamespace(finish_reason='stop',message=SimpleNamespace(content=json.dumps(model_json())))])
    fake=SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    config={'LLM_MODEL_NAME':'text-model','MULTIMODAL_VISION_MODEL':'vision-model','MULTIMODAL_ENABLED':True,'MULTIMODAL_VISION_API_STYLE':'chat'}
    r=analyze_frame(project,project['frames'][0],'test',tmp_path,config,fake)
    assert calls[0]['model']=='vision-model' and r['model']=='vision-model'
    config['MULTIMODAL_ENABLED']=False
    with pytest.raises(ValueError,match='MULTIMODAL_ENABLED'):analyze_frame(project,project['frames'][0],'test',tmp_path,config,fake)
    assert len(calls)==1


def test_null_model_scores_preserve_unknown_reasons():
    value=model_json();value['scores']['visibility']['score']=None
    result=validate_response(value,['inventory','image:photo.jpg','document:report.txt'],True,True)
    assert 'visibility' not in result['scores']
    assert result['unknown_scores']['visibility']=='clear view'
    assert result['scores']['market']['score']==70
