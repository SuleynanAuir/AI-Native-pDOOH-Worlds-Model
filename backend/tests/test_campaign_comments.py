import copy
import pytest
from app.audience import campaign_comments as c

def people():
 return [dict(agent_id=0,assigned_style=c.STYLES[0],profile={'current_need':'赶路','preferences':'效率','purchasing_power':'中等预算'}),dict(agent_id=1,assigned_style=c.STYLES[1],profile={'current_need':'等车','preferences':'实用','purchasing_power':'预算有限'})]
def rows():
 return [{'agent_id':0,'short_comment':'跑步口号太泛，广告没说适合新手还是常跑的人。','ad_anchor':'跑步','ad_focus':'人群定位','style':c.STYLES[0],'decision_axis':'任务相关','decision_hint':'测试极简通勤场景提示，观察是否能被快速辨认。','profile_fields':['current_need','preferences']},{'agent_id':1,'short_comment':'舒适是偏软还是偏稳？这广告的功能解释还不清楚。','ad_anchor':'舒适','ad_focus':'功能证据','style':c.STYLES[1],'decision_axis':'功能适配','decision_hint':'在候车视角测试功能说明，核查真实停留机会。','profile_fields':['current_need','preferences']}]
def test_comments_keep_style_profile_and_reject_templates_scores_and_unknown_fields():
 output=rows();output[0]['interest']=99
 result=c.validate({'agents':output},people());assert 'interest' not in result[0]
 for mutate in [lambda r:r[0].update(short_comment='如果价格合适我可能会去了解一下这双鞋。'),lambda r:r[0].update(short_comment='一双只要99元，我一定会买下来每天穿。'),lambda r:r[1].update(short_comment=r[0]['short_comment']),lambda r:r[0].update(profile_fields=['preferences','invented_income']),lambda r:r[0].update(style='族群口音')]:
  bad=copy.deepcopy(rows());mutate(bad)
  with pytest.raises(ValueError):c.validate({'agents':bad},people())
def test_near_duplicates_and_same_opening_are_not_only_exact_text_dedup():
 assert c.similarity('跑步口号太泛，广告没说适合新手还是常跑的人。','跑步口号太泛，广告没说明适合新手还是常跑的人！')>.72
 with pytest.raises(ValueError):c.validate({'agents':rows()},people(),[rows()[0]['short_comment']])
def test_generation_checkpoints_are_reused_without_overwriting_long_report(tmp_path):
 source=dict(scene_title='test',campaign={'title':'Nike','message':'日常跑步与舒适运动'},agents={str(p['agent_id']):dict(**p,interest=30,favorability=50,interpretation='任务',decision_implications='试验') for p in people()})
 before=copy.deepcopy(source);calls=[]
 def fake(config,prompt,payload,**kwargs):
  calls.append(payload);values=rows()
  for row,person in zip(values,payload['agents']):row['style']=person['assigned_style']
  return {'agents':values}
 one=c.generate_scene(source,{'LLM_MODEL_NAME':'test'},tmp_path,model=fake)
 two=c.generate_scene(source,{'LLM_MODEL_NAME':'test'},tmp_path,model=fake)
 assert len(calls)==1 and one['agents']==two['agents'] and source==before
 assert set(one['styles'])=={c.STYLES[0],c.STYLES[3]}

def test_partial_retry_preserves_accepted_person_and_original_ids(tmp_path):
 source=dict(scene_title='test',campaign={'title':'Nike','message':'日常跑步与舒适运动'},agents={str(p['agent_id']):dict(**p,interest=30,favorability=50,interpretation='任务',decision_implications='试验') for p in people()})
 calls=[]
 def fake(config,prompt,payload,**kwargs):
  calls.append(payload)
  selected=payload['agents'] if len(calls)>1 else payload['agents'][:1]
  return {'agents':[{**rows()[p['agent_id']],'style':p['assigned_style']} for p in selected]}
 result=c.generate_scene(source,{'LLM_MODEL_NAME':'test'},tmp_path,model=fake)
 assert len(result['agents'])==2 and len(calls)==2
 assert calls[1]['required_agent_ids']==[1]
 assert result['agents']['0']['short_comment']==rows()[0]['short_comment']

def test_api_binds_comments_to_completed_campaign_and_scene(tmp_path):
 from app import create_app
 from app.audience.world import write_json
 app=create_app();app.config.update(TESTING=True,UPLOAD_FOLDER=str(tmp_path));client=app.test_client()
 identifier='a'*32;sid='b'*32;directory=tmp_path/'campaign_experiments'/identifier
 directory.mkdir(parents=True);write_json(directory/'state.json',{'spec':{'scene_ids':[sid]}})
 url=f'/api/world/campaign-experiments/{identifier}/short-comments'
 assert client.get(url).json['data']['status']=='not_started'
 assert client.post(url,json={}).status_code==400
 assert client.get(url+'/scenes/'+sid).status_code==400
 target=directory/'short_comments'/f'v{c.VERSION}';target.mkdir(parents=True)
 write_json(target/'state.json',{'status':'completed'});write_json(target/f'{sid}.json',{'agents':{'0':rows()[0]}})
 assert client.get(url+'/scenes/'+sid).json['data']['agents']['0']['agent_id']==0
 assert client.get(url+'/scenes/'+'c'*32).status_code==400


def test_ad_review_requires_actual_copy_and_rejects_unprovided_visuals_and_irrelevant_transit_demands():
 creative='NIKE RUNNING 日常跑步与舒适运动'
 assert c.validate({'agents':rows()},people(),creative=creative)
 for comment,anchor in [('这则广告满屏跑步场景，看起来字太小了。','跑步'),('跑步广告没告诉我换乘口在哪，信息太少了。','跑步'),('限时优惠听着不错，但具体适用条件呢？','限时优惠')]:
  bad=copy.deepcopy(rows());bad[0].update(short_comment=comment,ad_anchor=anchor)
  with pytest.raises(ValueError):c.validate({'agents':bad},people(),creative=creative)
