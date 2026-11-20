from copy import deepcopy
import pytest
from app import create_app
from app.audience.day_cycle import DEFAULT, validate_day_cycle, schedule, attendance
from app.audience.world import scene, encounter_conditions
from app.audience.cohorts import summarize


def test_full_day_boundaries_and_multiple_dates():
    slots = schedule(validate_day_cycle({'days': 2, 'start_date': '2026-12-31'}))
    assert len(slots) == 48
    assert [s['hour'] for s in slots[:24]] == list(range(24))
    assert slots[0]['date'] == '2026-12-31' and slots[24]['date'] == '2027-01-01'
    assert slots[7]['period'] == slots[9]['period'] == 'morning'
    assert slots[10]['period'] == 'daytime'
    assert slots[17]['period'] == slots[18]['period'] == 'evening'
    assert slots[19]['period'] == slots[22]['period'] == 'night'
    assert slots[23]['period'] == 'quiet'


def test_overnight_period_and_holiday_window():
    config = deepcopy(DEFAULT)
    config['periods']['night'] = dict(start=22, end=2)
    config['holiday'] = dict(id='custom', name='社区夜间节', description='居民夜间活动假设', start_hour=22, end_hour=2, commute_factor=.5, leisure_factor=2)
    slots = schedule(validate_day_cycle(config))
    assert [s['hour'] for s in slots if s['holiday_active']] == [0, 1, 22, 23]
    assert slots[0]['period'] == 'night' and slots[2]['period'] == 'quiet'
    assert slots[7]['activity_factor'] == 1
    assert slots[23]['activity_factor'] == 2


@pytest.mark.parametrize('patch', [dict(days=True), dict(days=0), dict(days=4), dict(start_date='2026-02-30'), dict(start_date='20261225'), dict(start_date='9999-12-31', days=3), dict(holiday=None), dict(holiday={'id':'bad'}), dict(holiday={'id':'custom','name':''}), dict(holiday={'leisure_factor':float('nan')}), dict(holiday={'commute_factor':False}), dict(holiday={'start_hour':24}), dict(periods={})])
def test_invalid_configuration(patch):
    with pytest.raises(ValueError):validate_day_cycle(patch)


def test_overlapping_periods_rejected():
    config = deepcopy(DEFAULT)
    config['periods']['night'] = dict(start=18, end=23)
    with pytest.raises(ValueError):validate_day_cycle(config)
    assert DEFAULT['periods']['night']['start'] == 19


def test_holiday_affects_opportunities_not_weights_and_is_not_calendar_inference():
    base = scene(day_cycle={'start_date':'2026-12-25'})
    holiday = scene(day_cycle={'holiday':{'id':'christmas'}})
    assert not base['schedule'][8]['holiday_active']
    assert base['agents'] == holiday['agents']
    assert holiday['schedule'][8]['scheduled_population'] < base['schedule'][8]['scheduled_population']
    assert holiday['schedule'][20]['scheduled_population'] > base['schedule'][20]['scheduled_population']
    a = base['agents'][0]
    slot = holiday['schedule'][20]
    assert attendance(a, slot, 42) == attendance({**a,'represented_population':99999}, slot, 42)
    assert '圣诞节' in encounter_conditions(a,base['screens'][0],21,42,slot)['current_task']


def test_scheduled_population_and_away_are_not_non_attention():
    world = scene(total_population=30000, day_cycle={})
    assert world['schema_version'] == 5 and world['rounds'] == 24
    assert world == scene(total_population=30000, day_cycle={})
    for slot in world['schedule']:
        snapshot = []
        for a in world['agents']:
            active = attendance(a,slot,42)['present']
            snapshot.append({**a, 'reaction':'watch' if active else 'away', 'dwell_seconds':5 if active else None})
        result = summarize(snapshot)
        assert result['total_population'] == 30000
        assert sum(result['weighted_counts'].values()) == 30000
        assert result['active_population'] == slot['scheduled_population']
        assert result['weighted_mean_dwell_seconds'] == (5 if slot['scheduled_agents'] else None)
        assert result['weighted_counts']['passing'] == 0
    assert world['schedule'][8]['scheduled_population'] > world['schedule'][3]['scheduled_population']


def test_day_api_preview_no_provider(tmp_path):
    app=create_app();app.config.update(TESTING=True,UPLOAD_FOLDER=str(tmp_path),LLM_API_KEY=None)
    c=app.test_client()
    assert c.get('/api/world/scene').json['data']['rounds']==24
    assert len(c.get('/api/world/day-presets').json['data']['holidays'])>=7
    body=dict(agent_count=100,total_population=30000,day_cycle=dict(days=3,holiday={'id':'christmas'}))
    result=c.post('/api/world/preview',json=body)
    assert result.status_code==200 and result.json['data']['rounds']==72
    assert len(result.json['data']['schedule'])==72
    body['day_cycle']['days']=4
    assert c.post('/api/world/runs',json=body).status_code==400
    assert not list(tmp_path.glob('worlds/*/state.json'))
