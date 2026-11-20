import json
from pathlib import Path
import pytest
from app import create_app
from app.audience.world import scene,parse_decision,encounter_position,write_json,read_json
from app.audience.world import encounter_conditions,validate_encounter_decision


def test_scene_seed_and_groups():
    a=scene(100,4,42)
    assert a==scene(100,4,42)
    assert len({p['group'] for p in a['agents']})==12
    assert len(a['screens'])==3 and a['is_synthetic']
    assert all(0<=p['x']<=1000 and 0<=p['y']<=590 for p in a['agents'])


def test_oasis_reaction_contract():
    assert parse_decision('```json\n{"reaction":"passing","reason":"赶路","dwell_seconds":12}\n```')['dwell_seconds']==0
    for raw in ['{}','{"reaction":"purchase","reason":"x"}','{"reaction":"watch","reason":"x","dwell_seconds":99}','{"reaction":"watch","reason":"x","dwell_seconds":"NaN"}']:
        with pytest.raises((ValueError,KeyError)):parse_decision(raw)


def test_scene_positions_are_deterministic_adaptation():
    s=scene()['screens'][0]
    assert encounter_position(s,0,1)==encounter_position(s,0,1)
    assert encounter_position(s,0,1)!=encounter_position(s,0,2)


def test_encounters_are_seeded_assumptions_not_income_rules():
    world=scene();a=world['agents'][0];s=world['screens'][0]
    encounter=encounter_conditions(a,s,1,42)
    assert encounter==encounter_conditions(a,s,1,42)
    changed={**a,'represented_population':999,'audience_profile':{**a['audience_profile'],'economic_context':'different','purchasing_power':'different'}}
    assert encounter==encounter_conditions(changed,s,1,42)
    blocked=encounter_conditions(a,{**s,'obstruction':1},1,42)
    assert blocked['line_of_sight'] is False and blocked['available_seconds']==0
    with pytest.raises(ValueError):validate_encounter_decision(dict(reaction='glance',dwell_seconds=1),blocked)
    with pytest.raises(ValueError):validate_encounter_decision(dict(reaction='watch',dwell_seconds=31),dict(line_of_sight=True,available_seconds=30))
    assert validate_encounter_decision(dict(reaction='passing',dwell_seconds=0),blocked)['reaction']=='passing'


def test_world_api_preview_and_replay(tmp_path):
    app=create_app();app.config.update(TESTING=True,UPLOAD_FOLDER=str(tmp_path));c=app.test_client()
    assert c.get('/api/world/scene').json['data']['decision_source'].startswith('OASIS')
    assert c.get('/api/world/latest').json['data'] is None
    rid='a'*32;path=tmp_path/'worlds'/rid;path.mkdir()
    write_json(path/'state.json',dict(id=rid,status='completed',snapshots=[],events=[]))
    write_json(path/'control.json',dict(paused=False,stop=False))
    assert c.get('/api/world/latest').json['data']['id']==rid
    assert c.get('/api/world/runs/'+rid).status_code==200
    assert c.get('/api/world/runs/invalid').status_code==400
    assert c.post('/api/world/runs',json={'population':100000}).status_code==400
    assert c.post('/api/world/runs',json={'population':True}).status_code==400
    assert c.post('/api/world/runs/'+rid+'/control',json={'command':'delete'}).status_code==400
