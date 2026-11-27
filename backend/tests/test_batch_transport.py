import asyncio,json,sqlite3
from types import SimpleNamespace
from app.audience.batch_transport import BatchInterviews


def test_transport_bounds_requests_and_records_each_response(tmp_path):
    active=0;peak=0
    async def create(**kwargs):
        nonlocal active,peak
        active+=1;peak=max(peak,active)
        await asyncio.sleep(.01)
        active-=1
        return SimpleNamespace(choices=[SimpleNamespace(finish_reason='stop',message=SimpleNamespace(content=kwargs['messages'][-1]['content']))])
    client=SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    config=SimpleNamespace(LLM_BASE_URL='https://example.test',LLM_MODEL_NAME='test')
    async def exercise():
        transport=BatchInterviews(tmp_path,config,client=client)
        await transport.step([str(i) for i in range(20)])
    asyncio.run(exercise())
    assert peak==8
    with sqlite3.connect(tmp_path/'batch-traces.db') as db:rows=db.execute('SELECT user_id,info FROM trace ORDER BY user_id').fetchall()
    assert [(i,json.loads(info)['response']) for i,info in rows]==[(i,str(i)) for i in range(20)]
