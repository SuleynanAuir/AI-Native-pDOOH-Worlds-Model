import copy
import json
import pytest
from app import create_app
from app.audience.cohorts import DEFAULT_SEGMENTS,representatives,summarize
from app.audience.world import scene


def test_hundred_representatives_of_ten_thousand():
    a,g=representatives(100,10000)
    assert len(a)==100 and len(g)==12
    assert sum(x['represented_population'] for x in a)==10000
    assert sum(x['population'] for x in g)==10000
    assert sum(x['agent_count'] for x in g)==100
    assert len({json.dumps(x['audience_profile'],sort_keys=True) for x in a})==100
    for group in g:
        cohort=[x for x in a if x['group']==group['id']]
        assert sum(x['represented_population'] for x in cohort)==group['population']
        assert len(cohort)==group['agent_count']
        assert all(x['represented_population']>=1 for x in cohort)
    assert (a,g)==representatives(100,10000)


@pytest.mark.parametrize('total,count',[(10000,100),(12345,97),(1000000,200),(100,100),(10001,12)])
def test_weights_conserved_and_capped(total,count):
    agents,groups=representatives(count,total)
    assert sum(a['represented_population'] for a in agents)==total
    assert all(g['agent_count']<=g['population'] for g in groups)
    assert sum(a['weight'] for a in agents)==pytest.approx(1)


def test_rare_cohort_not_oversampled_and_zero_share_excluded():
    groups=copy.deepcopy(DEFAULT_SEGMENTS[:3])
    groups[0]['share']=1;groups[1]['share']=100;groups[2]['share']=0
    agents,cohorts=representatives(100,101,segments=groups)
    assert cohorts[0]['population']==1 and cohorts[0]['agent_count']==1
    assert cohorts[2]['population']==0 and cohorts[2]['agent_count']==0
    assert sum(a['represented_population'] for a in agents)==101


def test_weighted_results_not_raw_agent_count():
    agents=[dict(id=0,group='a',represented_population=100,reaction='watch',dwell_seconds=10,screen_id='s1'),dict(id=1,group='b',represented_population=900,reaction='passing',dwell_seconds=0,screen_id='s2')]
    summary=summarize(agents)
    assert summary['noticed_population']==100
    assert summary['notice_rate']==.1
    assert summary['weighted_mean_dwell_seconds']==1
    assert summary['weighted_counts']['watch']==100
    assert summary['agent_counts']['watch']==1
    assert sum(s['population'] for s in summary['screens'].values())==1000
    assert summarize(agents,False)['weighted_counts']['unknown']==1000
    agents[0].update(reaction='unknown',dwell_seconds=None)
    assert summarize(agents)['weighted_counts']['unknown']==100
    assert summarize(agents)['weighted_mean_dwell_seconds']==0


@pytest.mark.parametrize('count,total',[(201,10000),(100,99),(100,1000001),(True,10000),(4,10000)])
def test_invalid_sizes(count,total):
    with pytest.raises(ValueError):representatives(count,total)


def test_invalid_personas_and_sources_rejected():
    for change in [lambda g:g[0].update(share=float('nan')),lambda g:g[0].update(profile={}),lambda g:g[1].update(id=g[0]['id']),lambda g:g[0].update(source='')]:
        groups=copy.deepcopy(DEFAULT_SEGMENTS);change(groups)
        with pytest.raises(ValueError):representatives(100,10000,segments=groups)


def test_preview_endpoint_never_calls_llm(tmp_path):
    app=create_app();app.config.update(TESTING=True,UPLOAD_FOLDER=str(tmp_path),LLM_API_KEY=None)
    c=app.test_client()
    r=c.post('/api/world/preview',json={'agent_count':100,'total_population':30000,'rounds':2})
    assert r.status_code==200
    assert r.json['data']['schema_version']==5
    assert len(r.json['data']['agents'])==100
    assert sum(a['represented_population'] for a in r.json['data']['agents'])==30000
    assert not list(tmp_path.glob('worlds/*/state.json'))
    assert len(c.get('/api/world/segments').json['data'])==12
    assert c.post('/api/world/runs',json={'agent_count':100,'total_population':99}).status_code==400
