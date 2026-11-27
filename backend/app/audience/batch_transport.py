"""Small bounded model client; no social platform or embedding-model runtime."""
import asyncio
import json
import sqlite3


class BatchInterviews:
    def __init__(self,directory,config,client=None):
        if client is None:
            from openai import AsyncOpenAI
            client=AsyncOpenAI(api_key=config.LLM_API_KEY,base_url=config.LLM_BASE_URL,timeout=90,max_retries=1)
        self.client=client;self.config=config;self.database=directory/'batch-traces.db';self.limit=asyncio.Semaphore(8)
        with sqlite3.connect(self.database) as db:
            db.execute('CREATE TABLE IF NOT EXISTS trace (user_id INTEGER, action TEXT, info TEXT)')

    async def step(self,prompts):
        async def one(slot,prompt):
            extra={'extra_body':{'thinking':{'type':'disabled'}}} if 'deepseek.com' in self.config.LLM_BASE_URL else {}
            async with self.limit:
                response=await self.client.chat.completions.create(model=self.config.LLM_MODEL_NAME,max_tokens=4096,temperature=.6,response_format={'type':'json_object'},messages=[{'role':'system','content':'你是合成人群批量推演员。逐人使用输入画像，不能将某一人的人设套用给其他人。必须返回可验证的JSON决策，不编造真实行为。'},{'role':'user','content':prompt}],**extra)
            choice=response.choices[0]
            if choice.finish_reason!='stop':raise ValueError('批量模型输出不完整')
            return slot,json.dumps({'prompt':prompt,'response':choice.message.content},ensure_ascii=False)
        results=await asyncio.gather(*(one(i,prompt) for i,prompt in enumerate(prompts)))
        with sqlite3.connect(self.database) as db:
            db.executemany('INSERT INTO trace VALUES (?,\'interview\',?)',results)

    async def close(self):
        await self.client.close()
