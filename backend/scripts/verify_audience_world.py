"""Verify a completed weighted OASIS replay against its native SQLite trace.

Usage: PYTHONPATH=backend python3 backend/scripts/verify_audience_world.py RUN_DIR
"""
import json
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.audience.cohorts import summarize
from app.audience.day_cycle import attendance
from app.audience.mobility import movement_summary,with_viewing_stop
from app.audience.world import parse_decision, validate_encounter_decision


def assert_recorded_fields(recorded, recomputed):
    # Older replays omit newly added zero-count categories and active_population.
    if isinstance(recorded, dict):
        for key, value in recorded.items():
            assert key in recomputed
            assert_recorded_fields(value, recomputed[key])
    else:
        assert recorded == recomputed


def verify(directory):
    directory = Path(directory)
    state = json.loads((directory / 'state.json').read_text())
    assert state['status'] == 'completed', 'Run must be completed'
    scene = state['scene']
    count, total = scene['agent_count'], scene['total_population']
    assert len(state['snapshots']) == scene['rounds'] + 1
    assert len(state['events']) == count * scene['rounds']
    trace_ids = set()
    with sqlite3.connect(directory / 'oasis.db') as db:
        counts = dict(db.execute('SELECT action,COUNT(*) FROM trace GROUP BY action'))
        assert counts['sign_up'] == count
        assert counts.get('interview', 0) == sum(e.get('trace_id') is not None for e in state['events'])
        if scene.get('schedule'):
            assert counts.get('interview', 0) == state['llm_decisions'] == (sum(bool(j['encounter']) for r in scene['mobility_rounds'] for j in r.values()) if scene.get('mobility_rounds') else sum(s['scheduled_agents'] for s in scene['schedule']))
        for event in state['events']:
            if scene.get('schedule'):
                slot = scene['schedule'][event['round']-1]
                assert event['time'] == slot['time'] and event['day'] == slot['day']
            if event.get('trace_id') is None:
                if event['decision_source']=='spatial_route':
                    trip=scene['mobility_rounds'][event['round']-1][str(event['agent_id'])]
                    assert trip['encounter'] is None and event['reaction']=='unexposed'
                    continue
                assert event['decision_source'] == 'scenario_schedule' and event['reaction'] == 'away'
                slot = scene['schedule'][event['round']-1]
                assert not attendance(scene['agents'][event['agent_id']], slot, scene['seed'])['present']
                continue
            assert event['trace_id'] not in trace_ids
            trace_ids.add(event['trace_id'])
            user, action, info = db.execute('SELECT user_id,action,info FROM trace WHERE rowid=?', (event['trace_id'],)).fetchone()
            assert user == event['agent_id'] and action == 'interview'
            assert event['represented_population'] == scene['agents'][user]['represented_population']
            raw = json.loads(info)
            if scene.get('schedule'):
                context = json.loads(raw['prompt'].split('场景数据：', 1)[1])
                assert context['round'] == event['round']
                assert context['time_context']['time'] == event['time']
                assert context['time_context']['holiday_name'] == slot['holiday_name']
                assert context['activity']['present'] is True
                if scene.get('neighborhood'):
                    trip=scene['mobility_rounds'][event['round']-1][str(user)]
                    assert context['journey']=={k:v for k,v in trip.items() if k not in ('waypoints','screen_opportunities')}
                    assert trip['encounter']['screen_id']==event['screen_id']
                    assert event['encounter']['minute']==trip['encounter']['minute']
            if scene.get('locality'):
                if not scene.get('schedule'):
                    context = json.loads(raw['prompt'].split('场景数据：', 1)[1])
                for field in ('country','city','community','venue_type'):
                    assert context['regional_context'][field] == scene['locality'][field]
                assert context['local_audience'] == scene['agents'][user]['local_context']
                assert context['source_ids'] == scene['agents'][user]['source_ids']
                allowed=set(scene['audience_template']['used_source_ids'])
                assert all(s['id'] in allowed for s in context['regional_context']['sources'])
            try:
                decision = parse_decision(raw['response'])
                if 'encounter' in event:
                    validate_encounter_decision(decision, event['encounter'])
            except (ValueError, TypeError):
                assert event['reaction'] == 'unknown'
            else:
                for field in ('reaction', 'reason', 'dwell_seconds'):
                    assert event[field] == decision[field], f'Trace differs: {field}'
    for snapshot in state['snapshots']:
        assert len(snapshot['agents']) == count
        assert sum(a['represented_population'] for a in snapshot['agents']) == total
        if snapshot.get('slot'):
            slot = snapshot['slot']
            assert slot == scene['schedule'][snapshot['round']-1]
            assert snapshot['summary']['active_population'] == slot['scheduled_population']
            for agent in snapshot['agents']:
                assert (agent['reaction'] != 'away') == attendance(agent, slot, scene['seed'])['present']
        if scene.get('neighborhood') and snapshot['round']>0:
            trips=scene['mobility_rounds'][snapshot['round']-1]
            for agent in snapshot['agents']:
                trip=trips.get(str(agent['id']))
                if trip:
                    expected_trip=with_viewing_stop(trip,agent)
                    assert agent['journey']==expected_trip
                    assert bool(trip['encounter'])==(agent['screen_id'] is not None)
                else:assert 'journey' not in agent
            assert snapshot['movement_summary']==movement_summary(snapshot['agents'])
        expected = summarize(snapshot['agents'], snapshot['round'] > 0)
        if scene.get('schema_version', 0) >= 5:
            assert snapshot['summary'] == expected
        else:
            assert_recorded_fields(snapshot['summary'], expected)
    return dict(run_id=state['id'], engine=state['engine'], model=state['model'],
                agent_count=count, represented_population=total, rounds=scene['rounds'],
                native_trace_counts=counts, unique_verified_decisions=len(trace_ids),
                schedule_events=sum(e['decision_source']=='scenario_schedule' for e in state['events']),
                spatial_events=sum(e['decision_source']=='spatial_route' for e in state['events']),
                locality={k:v for k,v in scene.get('locality',{}).items() if k not in ('sources','cultural_notes','community_notes')},
                audience_template_id=scene.get('audience_template',{}).get('id'),
                invalid_decisions=state.get('decision_errors', 0),
                weighted_summaries=[s['summary'] for s in state['snapshots'][1:]],
                verified=['native trace matches replay', 'integer weight conservation',
                          'weighted summary recomputation', 'encounter constraint validation',
                          'hour and holiday context match native prompts'])


if __name__ == '__main__':
    print(json.dumps(verify(sys.argv[1]), ensure_ascii=False, indent=2))
