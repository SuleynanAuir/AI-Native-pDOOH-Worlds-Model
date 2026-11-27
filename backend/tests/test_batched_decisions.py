import pytest
from app.audience.batched_decisions import batches,parse_batch,prompt_for


def rows(n):
    return [dict(agent_id=i,persona='独立画像',context={'encounter':{'line_of_sight':True,'available_seconds':10}}) for i in range(n)]


def answer(ids):
    return {'decisions':[dict(agent_id=i,reaction='glance',dwell_seconds=2,reason='顺路看了一眼') for i in ids]}


def test_batch_request_reduction_and_individual_validation():
    people=rows(100)
    assert len(batches(people))==9
    assert [r['agent_id'] for batch in batches(people) for r in batch]==list(range(100))
    assert len(parse_batch(answer(range(12)),people[:12]))==12
    assert '独立画像' in prompt_for(people[:12])


@pytest.mark.parametrize('ids',[[0],[0,0],[0,3]])
def test_missing_duplicate_and_unknown_ids_rejected(ids):
    with pytest.raises(ValueError):parse_batch(answer(ids),rows(2))


def test_impossible_viewing_rejected():
    people=rows(1);people[0]['context']['encounter']['line_of_sight']=False
    with pytest.raises(ValueError):parse_batch(answer([0]),people)
    people[0]['context']['encounter']['line_of_sight']=True
    people[0]['context']['encounter']['available_seconds']=1
    with pytest.raises(ValueError):parse_batch(answer([0]),people)


def test_retry_only_invalid_people_without_discarding_valid_results():
    from app.audience.batched_decisions import recover_batch
    people=rows(4)
    raw=answer([0,1,1,2]);raw['decisions'][-1]['dwell_seconds']=20
    valid,retry=recover_batch(raw,people)
    assert list(valid)==[0]
    assert [r['agent_id'] for r in retry]==[1,2,3]


def test_shared_context_compaction_is_lossless():
    from app.audience.batched_decisions import batch_payload
    people=rows(12)
    for i,p in enumerate(people):p['context'].update(region={'evidence':'x'*2000},history=[i])
    compact=batch_payload(people)
    reconstructed=[{**r,'context':{**compact['common_context'],**r['context']}} for r in compact['agents']]
    assert reconstructed==people
    import json
    assert len(json.dumps(compact))<len(json.dumps(people))/4
