"""Screen planning API. Stored results are recomputed server-side, never trusted from a client."""
from io import BytesIO
import json
from pathlib import Path
import re
import uuid
from flask import Blueprint,current_app,jsonify,request,send_file
from . import store
from .planning import ingest,clean,plan,export_plan
from .analysis import analyze_frame,image_mime,public_image_url

planning_bp=Blueprint('planning',__name__)


def root(): return current_app.config['UPLOAD_FOLDER']

def body():
    value=request.get_json(silent=True)
    if not isinstance(value,dict): raise ValueError('请求必须为 JSON 对象')
    return value


def preview(project):
    from .simulation_workflow import signature
    return dict(id=project['id'],filename=project['filename'],source_sheet=project.get('source_sheet','UnfilteredFrames'),headers=project['headers'],frames=clean(project,{}),documents=project.get('documents',[]),photos=project.get('photos',{}),analyses=project.get('analyses',{}),result=project.get('result') if project.get('simulation_batch') and project['simulation_batch']['signature']==signature(project) and (project.get('result') or {}).get('options',{}).get('simulation_batch_id')==project['simulation_batch']['id'] else None)


@planning_bp.errorhandler(ValueError)
def invalid(error): return jsonify(success=False,error=str(error)),400

@planning_bp.errorhandler(FileNotFoundError)
def missing(error): return jsonify(success=False,error='项目或文件不存在'),404


@planning_bp.post('/import')
def import_inventory():
    upload=request.files.get('workbook')
    if not upload or not upload.filename.lower().endswith('.xlsx'): raise ValueError('请上传 .xlsx 原始库存')
    data=upload.read(25_000_001)
    if len(data)>25_000_000: raise ValueError('Excel 不能超过 25 MB')
    project=store.create(root(),ingest(data,Path(upload.filename).name,request.form.get('source_sheet')))
    return jsonify(success=True,data=preview(project))


@planning_bp.post('/sample')
def sample():
    sample=Path(__file__).resolve().parents[3]/'data/test.xlsx'
    project=store.create(root(),ingest(sample.read_bytes(),'data/test.xlsx',(request.get_json(silent=True) or {}).get('source_sheet')))
    return jsonify(success=True,data=preview(project))


@planning_bp.get('/<pid>')
def get_project(pid):
    with store.locked(root(),pid) as (_,project): return jsonify(success=True,data=preview(project))


@planning_bp.post('/<pid>/documents')
def documents(pid):
    uploads=request.files.getlist('documents')
    if not uploads: raise ValueError('请上传资料文件')
    with store.locked(root(),pid) as (path,project):
        added=[]
        for upload in uploads:
            raw=upload.read(8_000_001)
            if len(raw)>8_000_000: raise ValueError('每份资料不能超过 8 MB')
            name=Path(upload.filename).name
            if name.lower().endswith('.pdf'):
                import fitz
                try:
                    with fitz.open(stream=raw,filetype='pdf') as doc: text='\n'.join(p.get_text() for p in doc)
                except Exception: raise ValueError('无法提取 PDF 文字，请上传可搜索 PDF 或 TXT') from None
            elif name.lower().endswith(('.txt','.md')):
                try: text=raw.decode('utf-8-sig')
                except UnicodeDecodeError: raise ValueError('文本资料需为 UTF-8') from None
            else: raise ValueError('资料支持 PDF、TXT、MD')
            if not text.strip(): raise ValueError(f'{name} 没有可提取文字（扫描 PDF 请先 OCR）')
            added.append(dict(name=name,text=text[:60000],truncated=len(text)>60000,kind=request.form.get('kind','regional')))
        existing={d['name']:d for d in project.get('documents',[])}
        existing.update({d['name']:d for d in added})
        if len(existing)>10 or sum(len(d['text']) for d in existing.values())>120000: raise ValueError('最多 10 份资料，总提取文字不超过 120000 字符')
        project['documents']=list(existing.values()); project['analyses']={}; project.pop('result',None)
        store.save(path,project)
        return jsonify(success=True,data=preview(project))


@planning_bp.post('/<pid>/photos')
def photos(pid):
    uploads=request.files.getlist('photos')
    explicit=request.form.get('screen_id','').strip()
    if not uploads or len(uploads)>30: raise ValueError('每批上传 1–30 张图片')
    if explicit and len(uploads)!=1: raise ValueError('指定屏幕 ID 时每次只上传一张图片')
    with store.locked(root(),pid) as (path,project):
        matches=[]
        for upload in uploads:
            name=Path(upload.filename).name
            from urllib.parse import urlparse,unquote
            candidates=[f for f in project['frames'] if (f['screen_id']==explicit if explicit else Path(name).stem==f['screen_id'] or name==Path(unquote(urlparse(str(f['fields'].get('FRAMEIMAGEPATH') or '')).path)).name)]
            if len(candidates)!=1: raise ValueError(f'{name} 无法唯一关联，请使用屏幕 ID 命名或明确指定屏幕 ID')
            raw=upload.read(8_000_001)
            if len(raw)>8_000_000: raise ValueError('每张图片不能超过 8 MB')
            mime=image_mime(raw); matches.append((candidates[0]['screen_id'],name,raw,mime))
        for sid,name,raw,mime in matches:
            file=uuid.uuid4().hex+'.image'; (path/file).write_bytes(raw)
            project['photos'][sid]=dict(file=file,source=name,mime=mime)
            project['analyses'].pop(sid,None)
        project.pop('result',None); store.save(path,project)
        return jsonify(success=True,data=preview(project))


@planning_bp.post('/<pid>/image-link')
def image_link(pid):
    data=body(); sid=data.get('screen_id'); url=public_image_url(str(data.get('url','')))
    with store.locked(root(),pid) as (path,project):
        if sum(f['screen_id']==sid for f in project['frames'])!=1: raise ValueError('屏幕 ID 不存在或重复')
        project['photos'][sid]=dict(url=url,source=url)
        project['analyses'].pop(sid,None); project.pop('result',None); store.save(path,project)
        return jsonify(success=True,data=preview(project))


@planning_bp.post('/<pid>/feishu-image')
def feishu_image(pid):
    data=body(); token=str(data.get('file_token','')); sid=data.get('screen_id')
    if not re.fullmatch('[A-Za-z0-9_-]{10,200}',token): raise ValueError('需要飞书图片文件 token，文件夹链接不能直接分析')
    import os,httpx
    access=os.environ.get('FEISHU_TENANT_ACCESS_TOKEN')
    if not access: raise ValueError('服务端未配置 FEISHU_TENANT_ACCESS_TOKEN；也可下载后上传图片')
    with store.locked(root(),pid) as (path,project):
        if sum(f['screen_id']==sid for f in project['frames'])!=1: raise ValueError('屏幕 ID 不存在或重复')
        kind='medias' if data.get('kind')=='media' else 'files'
        try:
            with httpx.stream('GET',f'https://open.feishu.cn/open-apis/drive/v1/{kind}/{token}/download',headers={'Authorization':f'Bearer {access}'},timeout=30,follow_redirects=False) as response:
                if response.status_code!=200: raise ValueError('飞书图片获取失败，请检查 token、文件权限及应用授权')
                raw=bytearray()
                for chunk in response.iter_bytes():
                    raw.extend(chunk)
                    if len(raw)>8_000_000: raise ValueError('图片超过 8 MB')
        except httpx.HTTPError: raise ValueError('飞书服务暂不可用，请重试或上传图片') from None
        mime=image_mime(raw); file=uuid.uuid4().hex+'.image'; (path/file).write_bytes(raw)
        project['photos'][sid]=dict(file=file,source=f'feishu:{kind}:{token}',mime=mime)
        project['analyses'].pop(sid,None); project.pop('result',None); store.save(path,project)
        return jsonify(success=True,data=preview(project))


@planning_bp.post('/<pid>/analyze')
def analyze(pid):
    data=body(); ids=data.get('screen_ids'); focus=data.get('focus','视线、遮挡、自然观看机会、场所人群差异')
    if not isinstance(ids,list) or not 1<=len(ids)<=5 or any(not isinstance(x,str) for x in ids): raise ValueError('每次分析 1–5 个屏幕 ID')
    if not isinstance(focus,str) or len(focus)>4000: raise ValueError('分析重点限 4000 字符')
    results={}; errors={}
    with store.locked(root(),pid) as (path,project):
        for sid in dict.fromkeys(ids):
            matches=[f for f in project['frames'] if f['screen_id']==sid]
            if len(matches)!=1: errors[sid]='屏幕 ID 不存在或重复'; continue
            try:
                result=analyze_frame(project,matches[0],focus,path,current_app.config)
                project['analyses'][sid]=result; results[sid]=result
            except ValueError as exc: errors[sid]=str(exc)
            except Exception as exc:
                status=getattr(exc,'status_code',None)
                current_app.logger.warning('Multimodal analysis failed for screen %s (HTTP %s)',sid,status)
                hints={401:'API 密钥未通过认证',402:'账户余额或配额不足',403:'模型或接口访问被拒绝',404:'模型或接口地址不存在',429:'请求限流或配额不足'}
                errors[sid]=(f'模型服务返回 HTTP {status}：'+hints.get(status,'请检查模型能力或稍后重试')) if status else '模型服务连接失败或响应异常，请检查网络与模型配置'
        if results: project.pop('result',None)
        store.save(path,project)
    return jsonify(success=True,data=dict(results=results,errors=errors))


@planning_bp.post('/<pid>/plan')
def make_plan(pid):
    options=body()
    with store.locked(root(),pid) as (path,project):
        from .investment import campaign_evidence,settings,report,attach_plan
        cfg=settings(options)
        from .simulation_workflow import inspect
        _,evidence=inspect(root(),project,cfg['threshold'],require_ready=True)
        options['campaign_id']=evidence['campaign_id']
        options['simulation_only']=True
        options['simulation_batch_id']=evidence['batch']['id']
        result=plan(project,options)
        forecasts={}
        result['investment']=report(result,evidence,options,forecasts)
        attach_plan(result)
        project['result']=result; store.save(path,project)
    return jsonify(success=True,data=result)


@planning_bp.get('/campaigns')
def campaigns():
    items=[]
    for path in (Path(root())/'campaign_experiments').glob('*/state.json'):
        value=json.loads(path.read_text())
        if value.get('status')=='completed':
            items.append(dict(id=value['id'],campaign=value['spec']['campaign'],scenes=len(value['spec']['scene_ids']),updated_at=value.get('updated_at')))
    return jsonify(success=True,data=sorted(items,key=lambda v:v.get('updated_at') or '',reverse=True))


@planning_bp.get('/<pid>/export')
def export(pid):
    with store.locked(root(),pid) as (path,project):
        from .simulation_workflow import inspect
        _,evidence=inspect(root(),project,require_ready=True)
        if not project.get('result') or project['result'].get('options',{}).get('simulation_batch_id')!=evidence['batch']['id']:raise ValueError('请先根据本轮已完成的全天模拟生成第四步报告')
        strategy=request.args.get('strategy','investment')
        raw=export_plan(project,project['result'],strategy,path)
    return send_file(BytesIO(raw),mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',as_attachment=True,download_name=f'pDOOH-{strategy}.xlsx')


@planning_bp.route('/<pid>/coverage',methods=['GET','POST'])
def resolved_coverage(pid):
    from .simulation_workflow import begin,inspect
    from .coverage import start
    if request.method=='POST':
        batch=begin(root(),pid)
        start(current_app._get_current_object(),pid,batch['id'])
    with store.locked(root(),pid) as (_,project):value,_=inspect(root(),project)
    return jsonify(success=True,data=value)


@planning_bp.route('/<pid>/coverage/<cid>',methods=['GET','POST'])
def screen_coverage(pid,cid):
    from .coverage import start,status
    value=start(current_app._get_current_object(),pid,cid) if request.method=='POST' else status(root(),pid,cid)
    return jsonify(success=True,data={k:v for k,v in value.items() if k!='items'} | {'failures':[{ 'screen_id':sid,'error':i.get('error')} for sid,i in value.get('items',{}).items() if i.get('status')=='failed']})


@planning_bp.route('/<pid>/ad-setup', methods=['GET','POST'])
def ad_setup(pid):
    from .campaign_research import validate_campaign
    with store.locked(root(),pid) as (path,project):
        if request.method=='POST':
            value=body(); campaign=validate_campaign(value.get('campaign'))
            flow=value.get('vehicles_per_hour')
            if flow is not None and (type(flow) is not int or not 0<=flow<=3000):raise ValueError('车流须为0–3000的整数，或留空按地点估算')
            changed=project.get('ad_setup',{}).get('campaign')!=campaign
            project['ad_setup']={**project.get('ad_setup',{}),'campaign':campaign,'vehicles_per_hour':flow}
            if changed:project['ad_setup']['campaign_id']=None
            store.save(path,project)
        from .ad_setup import core_regions
        return jsonify(success=True,data={**{k:v for k,v in project.get('ad_setup',{}).items() if k!='traffic_estimates_before_road_evidence'},'core_regions':core_regions(clean(project,{}))})


@planning_bp.post('/<pid>/creative')
def upload_creative(pid):
    upload=request.files.get('image')
    if not upload:raise ValueError('请选择广告图片')
    raw=upload.read(8_000_001)
    if len(raw)>8_000_000:raise ValueError('广告图片不能超过8 MB')
    mime=image_mime(raw); identifier=uuid.uuid4().hex
    with store.locked(root(),pid) as (path,project):
        name=f'creative-{identifier}';(path/name).write_bytes(raw)
        asset={'id':identifier,'name':Path(upload.filename).name,'mime':mime,'url':f'/api/planning/{pid}/creative/{identifier}','status':'uploaded'}
        project.setdefault('ad_setup',{})['creative']=asset;store.save(path,project)
    return jsonify(success=True,data=asset)


@planning_bp.get('/<pid>/creative/<identifier>')
def creative_file(pid,identifier):
    if not re.fullmatch('[0-9a-f]{32}',identifier):raise ValueError('图片 ID 无效')
    with store.locked(root(),pid) as (path,project):
        file=path/f'creative-{identifier}'
        if not file.exists():raise FileNotFoundError()
        return send_file(file,mimetype=image_mime(file.read_bytes()))


@planning_bp.post('/<pid>/creative/analyze')
def analyze_creative(pid):
    from .ad_setup import describe_creative
    with store.locked(root(),pid) as (path,project):
        asset=project.get('ad_setup',{}).get('creative')
        if not asset:raise ValueError('请先上传广告图片')
        raw=(path/f'creative-{asset["id"]}').read_bytes()
    try: result=describe_creative(raw,asset['mime'],current_app.config)
    except Exception:raise ValueError('图片已保存，但图片理解暂不可用。可重试或手动描述物料内容。') from None
    with store.locked(root(),pid) as (path,project):
        if project['ad_setup']['creative']['id']!=asset['id']:raise ValueError('图片已更换，请重新分析')
        asset.update(result,status='analyzed');project['ad_setup']['creative']=asset;store.save(path,project)
    return jsonify(success=True,data=asset)


@planning_bp.post('/<pid>/traffic-estimate')
def traffic_estimate(pid):
    from .ad_setup import estimate_traffic,core_regions
    ids=body().get('screen_ids')
    if not isinstance(ids,list) or not 1<=len(ids)<=12 or any(not isinstance(x,str) for x in ids):raise ValueError('每批选择1–12块屏幕')
    with store.locked(root(),pid) as (_,project):
        inventory=clean(project,{})
        if not set(ids)<=set(f['screen_id'] for f in inventory):raise ValueError('屏幕 ID 不存在')
        areas=[r for r in core_regions(inventory) if set(r['screen_ids']) & set(ids)]
        expanded={sid for r in areas for sid in r['screen_ids']}
        if not set(ids)<=expanded:raise ValueError('屏幕缺少有效坐标')
        frames=[f for f in inventory if f['screen_id'] in expanded]
    try:
        result={}
        for area in areas:
            result.update(estimate_traffic([f for f in frames if f['screen_id'] in area['screen_ids']],current_app.config))
    except ValueError:raise
    except Exception:raise ValueError('车流估算服务暂不可用，可重试或手动设置，未填入默认预测值') from None
    with store.locked(root(),pid) as (path,project):
        setup=project.setdefault('ad_setup',{})
        if any(v.get('method_version')==3 for v in result.values()) and 'traffic_estimates_before_road_evidence' not in setup:
            setup['traffic_estimates_before_road_evidence']=dict(setup.get('traffic_estimates',{}))
        setup.setdefault('traffic_estimates',{}).update(result);store.save(path,project)
    return jsonify(success=True,data=result)
