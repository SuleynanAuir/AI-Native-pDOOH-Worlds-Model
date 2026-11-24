"""Start actual OASIS workers and serve their recorded scene snapshots."""
import os
from datetime import datetime,timezone
from pathlib import Path
import subprocess
import threading
import uuid
from flask import Blueprint,current_app,jsonify,request
from .world import scene,read_json,write_json
from .cohorts import DEFAULT_SEGMENTS, summarize, validate_segments
from .day_cycle import DEFAULT, HOLIDAYS, validate_day_cycle
from .locality import VENUES,validate_locality,locality_hash,scoped_sources,local_segment_fields,generate_template
from . import store

world_bp=Blueprint('world',__name__)
_start_lock=threading.Lock()


def root():
    path=Path(current_app.config['UPLOAD_FOLDER'])/'worlds';path.mkdir(parents=True,exist_ok=True);return path


def run_dir(rid):
    if len(rid)!=32 or any(c not in '0123456789abcdef' for c in rid):raise ValueError('无效运行 ID')
    path=root()/rid
    if not (path/'state.json').exists():raise FileNotFoundError()
    return path


@world_bp.errorhandler(ValueError)
def invalid(e):return jsonify(success=False,error=str(e)),400

@world_bp.errorhandler(FileNotFoundError)
def missing(e):return jsonify(success=False,error='运行记录不存在'),404


def template_root():
    path=Path(current_app.config['UPLOAD_FOLDER'])/'audience_templates';path.mkdir(parents=True,exist_ok=True);return path


@world_bp.get('/locality-options')
def locality_options():return jsonify(success=True,data=dict(venues=[dict(id=k,name=v[0]) for k,v in VENUES.items()]))


@world_bp.post('/local-audiences')
def local_audiences():
    data=request.get_json(silent=True)
    if not isinstance(data,dict):raise ValueError('需要区域与群体生成配置')
    locality=validate_locality(data.get('locality'))
    bind_geolocation({'locality':locality})
    try:result=generate_template(locality,data.get('group_count',12),current_app.config)
    except ValueError:raise
    except Exception as exc:
        status=getattr(exc,'status_code',None)
        return jsonify(success=False,error=f'区域画像模型服务失败'+(f'（HTTP {status}）' if status else '，请检查连接或稍后重试')),502
    result['id']=uuid.uuid4().hex
    write_json(template_root()/(result['id']+'.json'),result)
    return jsonify(success=True,data=result)


@world_bp.post('/location-inventory')
def location_inventory():
    data=request.get_json(silent=True) or {}
    if not isinstance(data,dict):raise ValueError('需要库存选择对象')
    if data.get('project_id'):
        if not isinstance(data['project_id'],str):raise ValueError('库存项目 ID 必须为字符串')
        with store.locked(current_app.config['UPLOAD_FOLDER'],data['project_id']) as (_,project):
            frames=project['frames'];documents=project.get('documents',[]);filename=project['filename']
    else:
        from .planning import ingest
        sample=Path(__file__).resolve().parents[3]/'data/test.xlsx'
        project=ingest(sample.read_bytes(),'data/test.xlsx');frames=project['frames'];documents=[];filename='data/test.xlsx'
    candidates=[]
    for f in frames:
        fields=f['fields']
        candidates.append(dict(screen_id=f['screen_id'],country=str(fields.get('ADDRESS_COUNTRY') or ''),city=str(fields.get('ADDRESS_LOCALITY') or ''),address=str(fields.get('ADDRESS_THOROUGHFARE') or ''),venue=str(fields.get('VENUE_TAXONOMY_VALUE') or ''),poi=str(fields.get('CLOSEST_POI') or fields.get('CLOEST_POI') or '')))
    return jsonify(success=True,data=dict(filename=filename,candidates=candidates,documents=[dict(id=f'inventory-doc-{i}',title=d['name'],text=d['text'][:8000],kind='document',country='',city='',community='',url='') for i,d in enumerate(documents[:10])],warning='库存城市字段可能是媒体市场而非行政城市；地址、POI 和社区范围需核对。资料未标明适用地区时不会参与生成。'))


def bind_locality(data):
    if 'locality' not in data:return
    data['locality']=validate_locality(data['locality'])
    bind_geolocation(data)
    tid=data.get('template_id')
    if not isinstance(tid,str) or len(tid)!=32 or any(c not in '0123456789abcdef' for c in tid):raise ValueError('请先按当前国家、社区和场所生成本地人群模板')
    path=template_root()/(tid+'.json')
    if not path.is_file():raise ValueError('本地人群模板不存在，请重新生成')
    template=read_json(path)
    if template['context_hash']!=locality_hash(data['locality']):raise ValueError('地区、场所或资料已变化，旧画像不能复用，请重新生成本地人群')
    data['segments']=data.get('segments',template['segments'])
    if not isinstance(data['segments'],list):raise ValueError('本地群体配置无效')
    for segment in data['segments']:
        if not isinstance(segment,dict):raise ValueError('本地群体配置无效')
        local_segment_fields(segment,template['used_source_ids'])
    data['segments']=validate_segments(data['segments'])
    data['audience_template']={k:v for k,v in template.items() if k not in ('segments','locality')}
    data['audience_template']['user_edited_segments']=data['segments']!=template['segments']


@world_bp.get('/scene')
def initial():return jsonify(success=True,data=scene(day_cycle={}))


@world_bp.get('/day-presets')
def day_presets():return jsonify(success=True,data=dict(default=DEFAULT,holidays=HOLIDAYS))


@world_bp.get('/segments')
def segments():return jsonify(success=True,data=DEFAULT_SEGMENTS)


@world_bp.post('/preview')
def preview():
    data=validated_config(request.get_json(silent=True))
    return jsonify(success=True,data=scene(data['agent_count'],data['rounds'],data['seed'],total_population=data['total_population'],segments=data.get('segments'),day_cycle=data.get('day_cycle'),locality=data.get('locality'),audience_template=data.get('audience_template'),mobility=data.get('mobility'),traffic_options=data.get('traffic_options'),geographic_context=data.get('geographic_context')))


@world_bp.get('/latest')
def latest():
    files=sorted(root().glob('*/state.json'),key=lambda p:p.stat().st_mtime,reverse=True)
    return jsonify(success=True,data=read_json(files[0]) if files else None)


def validated_config(data):
    if not isinstance(data,dict):raise ValueError('需要运行配置')
    data=dict(data)
    data.pop('geographic_context',None)
    data['agent_count']=data.get('agent_count',data.get('population',100))
    for name,default,minimum,maximum in [('agent_count',100,4,200),('total_population',10000,4,1000000),('rounds',4,1,72),('seed',42,0,2147483647)]:
        value=data.get(name,default)
        if isinstance(value,bool) or not isinstance(value,int) or not minimum<=value<=maximum:raise ValueError(f'{name} 必须是 {minimum}–{maximum} 的整数')
        data[name]=value
    if 'day_cycle' in data:
        data['day_cycle']=validate_day_cycle(data['day_cycle'])
        data['rounds']=24*data['day_cycle']['days']
    elif data['rounds']>12:raise ValueError('超过 12 轮请使用全天模拟配置')
    bind_locality(data)
    # Validate cohort allocation before creating a run or touching a provider.
    scene(data['agent_count'],data['rounds'],data['seed'],total_population=data['total_population'],segments=data.get('segments'),day_cycle=data.get('day_cycle'),locality=data.get('locality'),audience_template=data.get('audience_template'),mobility=data.get('mobility'),traffic_options=data.get('traffic_options'),geographic_context=data.get('geographic_context'))
    return data


@world_bp.post('/runs')
def start():
    data=validated_config(request.get_json(silent=True))
    screens=None;pid=data.get('project_id')
    if pid:
        with store.locked(current_app.config['UPLOAD_FOLDER'],pid) as (_,project):
            result=project.get('result')
            if not result:raise ValueError('库存项目需要先计算候选方案')
            frames=[f for f in result['frames'] if f['eligible']]
            if data.get('locality'):
                from .planning import country
                loc=data['locality']
                frames=[f for f in frames if country(f['fields'].get('ADDRESS_COUNTRY'))==country(loc['country']) and str(f['fields'].get('ADDRESS_LOCALITY') or '').casefold()==loc['city'].casefold()]
                # A local station scenario must not silently inherit a roadside screen.
                terms={'station':('station','transit','train','rail','bus'),'supermarket':('supermarket','grocery'),'mall':('mall','shopping'),'airport':('airport',),'street':('outdoor','street','billboard'),'office':('office',),'custom':()}
                if loc['venue_type']!='custom':frames=[f for f in frames if any(t in str(f['fields'].get('VENUE_TAXONOMY_VALUE') or '').lower() for t in terms[loc['venue_type']])]
            frames=frames[:3]
            if not frames:raise ValueError('当前区域与场所没有可用库存候选；请核对国家、城市、场所或取消库存模式')
            screens=[dict(id=f['screen_id'],name=str(f['fields'].get('CLOSEST_POI') or f['screen_id']),venue=f['fields'].get('VENUE_TAXONOMY_VALUE'),visibility=f['scores']['visibility']/100,obstruction=None,evidence=f['evidence'],audiences=f['analysis'].get('audiences',[])) for f in frames]
    backend=Path(__file__).resolve().parents[2]
    python=os.environ.get('OASIS_PYTHON') or str(backend/'.venv-oasis/bin/python')
    if not Path(python).is_file():raise ValueError('请安装 OASIS 独立环境并配置 OASIS_PYTHON')
    if not current_app.config.get('LLM_API_KEY'):raise ValueError('请先配置 LLM_API_KEY')
    with _start_lock:
        for path in root().glob('*/state.json'):
            old=read_json(path)
            if old['status'] in ('initializing','running','paused','queued'):
                try:
                    old_pid=read_json(path.parent/'process.json')['pid']
                    from .process_health import alive
                    if not alive(old_pid):continue
                except (OSError,TypeError):continue
                if old_pid:raise ValueError('已有 OASIS 运行，请先停止或等待完成')
        rid=uuid.uuid4().hex;path=root()/rid;path.mkdir()
        config=scene(data['agent_count'],data['rounds'],data['seed'],screens,data['total_population'],data.get('segments'),data.get('day_cycle'),data.get('locality'),data.get('audience_template'),data.get('mobility'),data.get('traffic_options'),data.get('geographic_context'))
        state=dict(id=rid,status='queued',engine='OASIS',current_round=0,scene=config,snapshots=[dict(round=0,agents=config['agents'],events=[],summary=summarize(config['agents'],False))],events=[],message='正在启动 OASIS 独立进程',project_id=pid)
        write_json(path/'state.json',state);write_json(path/'control.json',dict(paused=False,stop=False))
        with (path/'worker.log').open('w') as log:
            process=subprocess.Popen([python,str(backend/'scripts/run_audience_world.py'),str(path.resolve())],stdout=log,stderr=log,cwd=path.resolve(),start_new_session=True)
        # PID stored separately avoids racing the worker's atomic state updates.
        write_json(path/'process.json',{'pid':process.pid})
        def reap():
            code=process.wait()
            if code:
                try:
                    latest=read_json(path/'state.json')
                    if latest['status'] not in ('completed','failed','stopped'):
                        latest.update(status='failed',message=f'OASIS工作进程退出（状态 {code}），请检查独立环境；已完成屏幕保留')
                        write_json(path/'state.json',latest)
                except (OSError,ValueError):pass
        threading.Thread(target=reap,daemon=True).start()
    return jsonify(success=True,data=state),202


@world_bp.get('/runs/<rid>')
def status(rid):return jsonify(success=True,data=read_json(run_dir(rid)/'state.json'))


@world_bp.post('/runs/<rid>/control')
def control(rid):
    data=request.get_json(silent=True)
    if not isinstance(data,dict):raise ValueError('需要控制命令对象')
    command=data.get('command');path=run_dir(rid)
    if command not in ('pause','resume','stop'):raise ValueError('不支持的控制命令')
    if read_json(path/'state.json')['status'] in ('completed','failed','stopped'):raise ValueError('运行已结束，请开始新推演或使用回放控件')
    current=read_json(path/'control.json')
    if command=='stop':current['stop']=True
    else:current['paused']=command=='pause'
    write_json(path/'control.json',current)
    return jsonify(success=True,data=dict(command=command,boundary='当前轮次完成后生效'))


@world_bp.post('/runs/<rid>/traffic')
def traffic_replay(rid):
    from .traffic import build_traffic,validate_traffic
    import hashlib
    import json
    data=request.get_json(silent=True)
    if not isinstance(data,dict):raise ValueError('需要车辆与人群配置')
    path=run_dir(rid);state=read_json(path/'state.json')
    options=validate_traffic(data.get('traffic_options',state['scene'].get('traffic_options')))
    signature=hashlib.sha256(json.dumps(dict(options=options,round=state['current_round'],version=2),sort_keys=True).encode()).hexdigest()[:20]
    target=path/f'traffic-{signature}.json'
    if target.exists():result=read_json(target)
    else:
        result=build_traffic(state['scene'],options,state['snapshots'])
        result.update(source_run_id=rid,source_round=state['current_round'])
        # Cache writes may originate from multiple tabs; use unique temp files.
        temp=target.with_suffix('.'+uuid.uuid4().hex+'.tmp')
        temp.write_text(json.dumps(result,ensure_ascii=False,allow_nan=False),encoding='utf-8');temp.replace(target)
    return jsonify(success=True,data=result)


@world_bp.post('/traffic-preview')
def traffic_preview():
    from .traffic import build_traffic
    data=validated_config(request.get_json(silent=True))
    value=scene(data['agent_count'],data['rounds'],data['seed'],total_population=data['total_population'],segments=data.get('segments'),day_cycle=data.get('day_cycle'),locality=data.get('locality'),audience_template=data.get('audience_template'),mobility=data.get('mobility'),traffic_options=data.get('traffic_options'),geographic_context=data.get('geographic_context'))
    return jsonify(success=True,data=build_traffic(value))



def geo_root():
    path=Path(current_app.config['UPLOAD_FOLDER'])/'geolocations';path.mkdir(parents=True,exist_ok=True);return path


def geo_file(kind,identifier):
    if not isinstance(identifier,str) or len(identifier)!=32 or any(c not in '0123456789abcdef' for c in identifier):raise ValueError('地点记录 ID 无效')
    return geo_root()/f'{kind}-{identifier}.json'


def bind_geolocation(data):
    gid=data['locality'].get('geolocation_id')
    if not gid:return
    context=read_json(geo_file('lookup',gid))
    for key in ('country','city','community','venue_type'):
        if data['locality'][key]!=context['locality'][key]:raise ValueError('地区或场所已偏离坐标查证记录，请重新选择 Frame 定位')
    original=context['locality']['sources'][0]
    supplied=next((s for s in data['locality']['sources'] if s['id']==original['id']),None)
    if supplied!=original:raise ValueError('坐标地图证据被修改或删除；请重新应用查证地点，或解除坐标绑定')
    # Only persisted map evidence enters a scene; never trust client-provided geometry.
    data['geographic_context']=context


@world_bp.get('/location-config')
def location_config():
    mapricot=current_app.config.get('LOCATION_PROVIDER')=='mapricot'
    return jsonify(success=True,data=dict(enabled=bool(current_app.config.get('LOCATION_LOOKUP_ENABLED')) and (bool(current_app.config.get('MAPRICOT_API_KEY')) if mapricot else True),
        provider='mapricot' if mapricot else 'legacy',
        disclosure='Mapricot 接收经纬度和半径；密钥仅在服务端使用。区域大模型接收返回地址、设施和分区摘要，不接收密钥或完整工作簿。',
        policy_url='https://mapricot.com/docs/api-reference/',rate_limit='每轮执行地址与 POI 两类查询（失败最多重试一次），3 个并发；证据缓存 7 天，地图按当前视野加载'))



@world_bp.post('/geo-inventory')
def geo_inventory():
    from .geolocation import filtered_inventory
    from .workbook import read_workbook
    upload=request.files.get('file')
    if upload:
        if not str(upload.filename).lower().endswith('.xlsx'):raise ValueError('请上传 XLSX 工作簿')
        value=filtered_inventory(read_workbook(upload.read()),Path(upload.filename).name)
    else:
        data=request.get_json(silent=True) or {}
        if not isinstance(data,dict):raise ValueError('库存选择无效')
        if data.get('project_id'):
            if not isinstance(data['project_id'],str):raise ValueError('库存项目 ID 无效')
            with store.locked(current_app.config['UPLOAD_FOLDER'],data['project_id']) as (_,project):
                value=filtered_inventory(project.get('source_sheets',{}),project['filename'])
        else:
            path=Path(__file__).resolve().parents[3]/'data/test.xlsx'
            value=filtered_inventory(read_workbook(path.read_bytes()),'data/test.xlsx')
    value['id']=uuid.uuid4().hex;write_json(geo_file('inventory',value['id']),value)
    return jsonify(success=True,data=value)


@world_bp.post('/locate-frame')
def locate_frame():
    from .geolocation import map_evidence,interpret,resolved_context
    from .geographic_scene import geographic_network
    data=request.get_json(silent=True)
    if not isinstance(data,dict):raise ValueError('请选择 FilteredFrames 屏幕')
    inventory=read_json(geo_file('inventory',data.get('inventory_id')))
    frame=next((f for f in inventory['frames'] if f['key']==data.get('frame_key')),None)
    if not frame or frame['error']:raise ValueError(frame['error'] if frame else '所选 Frame 不存在')
    radius=data.get('radius_m',400)
    if type(radius) is not int or not 100<=radius<=600:raise ValueError('查询半径须为 100–600 米')
    if not current_app.config.get('LOCATION_LOOKUP_ENABLED'):
        return jsonify(success=False,error='外部地图查询尚未获准启用；当前仅完成本地 GEOM 解析，不会用模型猜测冒充查证',code='location_lookup_disabled'),409
    evidence=map_evidence(frame['coordinate'],radius,current_app.config,geo_root()/'map-cache')
    regional=None
    if data.get('region_id'):
        from .regions import fingerprint
        regional=read_json(geo_file('region',data['region_id']))
        if regional['fingerprint']!=fingerprint(inventory):raise ValueError('区域地图与当前工作簿不一致')
        association=next((f for f in regional['frames'] if f['key']==frame['key']),None)
        group=next((g for g in regional['groups'] if association and g['id']==association.get('region_id')),None)
        analysis=next((a for a in (regional.get('analysis') or {}).get('regions',[]) if group and a['id']==group['id']),None)
        evidence['regional_context']=dict(group=group,analysis=analysis,classification='区域地图线索与模型假设，不是人口调查')
    try:inference=interpret(frame,evidence,current_app.config)
    except ValueError:raise
    except Exception:return jsonify(success=False,error='地点模型服务失败，未生成或应用推测结果'),502
    result=resolved_context(frame,evidence,inference,uuid.uuid4().hex)
    # Validate usable geometry now, before offering to bind this location to a model.
    network,screens=geographic_network(result)
    result['network_summary']=dict(nodes=len(network['nodes']),edges=len(network['edges']),vehicle_paths=len(network['vehicle_paths']))
    result['workbook']=dict(filename=inventory['filename'],sheet=inventory['sheet'],frame_key=frame['key'])
    write_json(geo_file('lookup',result['id']),result)
    return jsonify(success=True,data=result)


_region_lock=threading.Lock()
_region_jobs=set()


@world_bp.get('/mapricot/<kind>')
def mapricot_document(kind):
    from .mapricot_provider import map_document
    # Raw MapLibre document, not the API envelope.
    return jsonify(map_document(kind,current_app.config))


@world_bp.post('/regions')
def start_region():
    from .regions import build,fingerprint
    from .mapricot_provider import enabled
    enabled(current_app.config)
    data=request.get_json(silent=True)
    if not isinstance(data,dict):raise ValueError('请选择库存')
    inventory=read_json(geo_file('inventory',data.get('inventory_id')))
    if inventory['valid_coordinates']>500:raise ValueError('单次最多 500 个坐标，请筛选库存')
    signature=fingerprint(inventory);rid=uuid.uuid4().hex;directory=geo_root();config=dict(current_app.config)
    with _region_lock:
        if signature in _region_jobs:raise ValueError('该库存正在查询，请等待当前任务')
        _region_jobs.add(signature)
        write_json(directory/f'region-{rid}.json',dict(id=rid,inventory_id=inventory['id'],fingerprint=signature,status='queued',queried_at=datetime.now(timezone.utc).isoformat(),completed=0,total=inventory['valid_coordinates'],frames=[],groups=[],pois=[]))
    def work():
        try:build(inventory,config,directory,rid)
        finally:
            with _region_lock:_region_jobs.discard(signature)
    threading.Thread(target=work,daemon=True).start()
    return jsonify(success=True,data=dict(id=rid)),202


@world_bp.get('/regions/latest/<inventory_id>')
def latest_region(inventory_id):
    from .regions import fingerprint
    signature=fingerprint(read_json(geo_file('inventory',inventory_id)))
    matches=[v for path in geo_root().glob('region-*.json') if (v:=read_json(path)).get('fingerprint')==signature]
    return jsonify(success=True,data=max(matches,key=lambda v:v.get('queried_at','')) if matches else None)


@world_bp.get('/regions/<rid>')
def get_region(rid):
    return jsonify(success=True,data=read_json(geo_file('region',rid)))


@world_bp.post('/regions/<rid>/analyze')
def analyze_region(rid):
    from .regions import analyze
    path=geo_file('region',rid);config=dict(current_app.config)
    with _region_lock:
        value=read_json(path)
        if value['status'] not in ('complete','partial'):raise ValueError('请等待地图查询完成')
        if 'analysis-'+rid in _region_jobs:raise ValueError('区域分析正在进行')
        _region_jobs.add('analysis-'+rid);value.update(analysis_status='running',analysis_error='');write_json(path,value)
    def work():
        try:
            def progress(partial):
                value.update(analysis=partial,analysis_completed=len(partial['regions']),analysis_total=len(value['groups']));write_json(path,value)
            result=analyze(value,config,progress=progress);value.update(analysis=result,analysis_status='complete')
        except Exception as exc:value.update(analysis_status='failed',analysis_error=str(exc) if isinstance(exc,ValueError) else '区域模型服务失败，请重试')
        finally:
            write_json(path,value)
            with _region_lock:_region_jobs.discard('analysis-'+rid)
    threading.Thread(target=work,daemon=True).start()
    return jsonify(success=True,data=dict(id=rid)),202


def comparison_root():
    path=Path(current_app.config['UPLOAD_FOLDER'])/'scene_library';path.mkdir(parents=True,exist_ok=True);return path


@world_bp.get('/comparison-scenes')
def comparison_catalog():
    items=[read_json(p) for p in comparison_root().glob('*/meta.json') if not p.parent.name.startswith('.')]
    return jsonify(success=True,data=sorted(items,key=lambda v:v['created_at']))


@world_bp.post('/comparison-scenes/import')
def comparison_import():
    from .comparison import import_run
    data=request.get_json(silent=True)
    if not isinstance(data,dict) or not isinstance(data.get('run_id'),str):raise ValueError('请选择已完成运行')
    return jsonify(success=True,data=import_run(comparison_root(),run_dir(data['run_id'])))


@world_bp.post('/comparison-scenes/preview')
def comparison_preview():
    from .comparison import publish
    from .traffic import build_traffic
    data=validated_config(request.get_json(silent=True))
    if not data.get('geographic_context'):raise ValueError('请先查证屏幕坐标，不能用示意地图冒充地点场景')
    value=scene(data['agent_count'],data['rounds'],data['seed'],total_population=data['total_population'],segments=data.get('segments'),day_cycle=data.get('day_cycle'),locality=data.get('locality'),audience_template=data.get('audience_template'),mobility=data.get('mobility'),traffic_options=data.get('traffic_options'),geographic_context=data['geographic_context'])
    return jsonify(success=True,data=publish(comparison_root(),value,build_traffic(value),'preview'))


@world_bp.get('/comparison-scenes/<identifier>')
def comparison_base(identifier):
    from .comparison import directory
    from .replay_response import replay_response
    return replay_response(directory(comparison_root(),identifier)/'base.json')


@world_bp.get('/comparison-scenes/<identifier>/hours/<int:round_num>')
def comparison_hour(identifier,round_num):
    from .comparison import directory
    path=directory(comparison_root(),identifier);meta=read_json(path/'meta.json')
    if not 1<=round_num<=meta['rounds']:raise ValueError('该场景没有此时段，不复用其他小时记录')
    from .replay_response import replay_response
    return replay_response(path/f'hour-{round_num}.json')


@world_bp.get('/runs/<rid>/summary')
def run_summary(rid):
    value=read_json(run_dir(rid)/'state.json')
    return jsonify(success=True,data={k:value.get(k) for k in ('id','status','current_round','llm_decisions','message','engine','model')})


def campaign_root():
    p=Path(current_app.config['UPLOAD_FOLDER'])/'campaign_experiments';p.mkdir(parents=True,exist_ok=True);return p


@world_bp.get('/campaign-presets')
def campaign_presets():
    from .campaign_research import PRESETS
    return jsonify(success=True,data=PRESETS)


@world_bp.post('/campaign-experiments')
def create_campaign_experiment():
    from .campaign import validate_request,start_job
    data=request.get_json(silent=True)
    spec=validate_request(data,comparison_root())
    if data.get('project_id'):
        with store.locked(current_app.config['UPLOAD_FOLDER'],data['project_id']) as (_,project):
            setup=project.get('ad_setup',{})
            if not setup.get('campaign'):raise ValueError('请先完成第二步广告设置')
            spec['campaign']=dict(setup['campaign'])
            creative=setup.get('creative')
            if creative:
                spec['campaign']['creative_asset']={k:creative[k] for k in ('id','name','url')}
                if creative.get('description'):spec['campaign']['creative_observation']=creative['description']
            spec['traffic_estimates']=setup.get('traffic_estimates',{})
            spec['traffic_manual']=setup.get('vehicles_per_hour')
            spec['project_id']=data['project_id']
    return jsonify(success=True,data=start_job(campaign_root(),comparison_root(),root(),spec,current_app.config)),202


@world_bp.get('/campaign-experiments/latest')
def latest_campaign_experiment():
    items=[read_json(p) for p in campaign_root().glob('*/state.json')]
    items=[s for s in items if s['status']=='completed']
    return jsonify(success=True,data=max(items,key=lambda s:s['created_at']) if items else None)


@world_bp.get('/campaign-experiments/<identifier>')
def campaign_experiment_status(identifier):
    from .campaign import job_dir
    return jsonify(success=True,data=read_json(job_dir(campaign_root(),identifier)/'state.json'))


def campaign_scene_path(identifier,sid):
    from .campaign import job_dir,valid_id
    p=job_dir(campaign_root(),identifier);state=read_json(p/'state.json')
    if state['spec'].get('coverage_only'):
        from .coverage import path as coverage_path
        folder=coverage_path(current_app.config['UPLOAD_FOLDER'],state['spec']['project_id'],identifier)
        from .replay_response import completed
        if valid_id(sid) not in completed(folder/'state.json'):raise ValueError('本轮该场景尚未完成24小时模拟')
        return folder/'scenes'/sid
    if state['status']!='completed':raise ValueError('广告实验尚未完整完成，不能应用部分场景')
    if valid_id(sid) not in state['spec']['scene_ids']:raise ValueError('此地点未参与该广告实验，请重新生成')
    return p/'scenes'/sid


@world_bp.get('/campaign-experiments/<identifier>/scenes/<sid>')
def campaign_scene(identifier,sid):
    from .replay_response import replay_response
    return replay_response(campaign_scene_path(identifier,sid)/'base.json')


@world_bp.get('/campaign-experiments/<identifier>/scenes/<sid>/hours/<int:round_num>')
def campaign_scene_hour(identifier,sid,round_num):
    p=campaign_scene_path(identifier,sid)
    from .replay_response import replay_response,rounds
    if not 1<=round_num<=rounds(p/'base.json'):raise ValueError('该场景没有此时段')
    from .replay_repair import campaign_hour
    return replay_response(p/f'hour-{round_num}.json',repair=lambda:campaign_hour(p,round_num,current_app.config['UPLOAD_FOLDER']))


@world_bp.post('/campaign-experiments/<identifier>/traffic')
def campaign_traffic_only(identifier):
    from .campaign import job_dir,validate_request,start_job
    previous=read_json(job_dir(campaign_root(),identifier)/'state.json')
    if previous['status']!='completed':raise ValueError('只能复用已完成的广告分析')
    data=request.get_json(silent=True)
    if not isinstance(data,dict):raise ValueError('需要车流设置')
    spec=validate_request(dict(campaign=previous['spec']['campaign'],scene_ids=data.get('scene_ids',previous['spec']['scene_ids']),vehicles_per_hour=data.get('vehicles_per_hour')),comparison_root())
    if not set(spec['scene_ids'])<=set(previous['spec']['scene_ids']):raise ValueError('新地点尚无广告分析，请先检索并分析')
    return jsonify(success=True,data=start_job(campaign_root(),comparison_root(),root(),spec,current_app.config,identifier)),202


@world_bp.get('/campaign-experiments/<identifier>/narratives')
def campaign_narrative_status(identifier):
    from .campaign_narratives import status
    return jsonify(success=True,data=status(campaign_root(),identifier))


@world_bp.post('/campaign-experiments/<identifier>/narratives')
def campaign_narrative_start(identifier):
    from .campaign_narratives import start
    return jsonify(success=True,data=start(campaign_root(),comparison_root(),root(),identifier,dict(current_app.config))),202


@world_bp.get('/campaign-experiments/<identifier>/narratives/scenes/<sid>')
def campaign_narrative_scene(identifier,sid):
    from .campaign_narratives import scene_result
    return jsonify(success=True,data=scene_result(campaign_root(),identifier,sid))


@world_bp.get('/campaign-experiments/<identifier>/narratives/report.txt')
def campaign_narrative_report(identifier):
    from flask import Response
    from .campaign_narratives import scene_result,report_text
    from .campaign import job_dir
    state=read_json(job_dir(campaign_root(),identifier)/'state.json')
    scope=request.args.get('scope','all')
    if scope not in ('all','groups'):raise ValueError('导出范围须为 all 或 groups')
    report=report_text([scene_result(campaign_root(),identifier,s) for s in state['spec']['scene_ids']],groups_only=scope=='groups')
    filename='audience-decision-brief.txt' if scope=='groups' else 'audience-ad-comments.txt'
    return Response(report,content_type='text/plain; charset=utf-8',headers={'Content-Disposition':f'attachment; filename="{filename}"'})


@world_bp.get('/campaign-experiments/<identifier>/short-comments')
def campaign_short_comment_status(identifier):
    from .campaign_comments import status
    return jsonify(success=True,data=status(campaign_root(),identifier))


@world_bp.post('/campaign-experiments/<identifier>/short-comments')
def campaign_short_comment_start(identifier):
    from .campaign_comments import start
    return jsonify(success=True,data=start(campaign_root(),identifier,dict(current_app.config))),202


@world_bp.get('/campaign-experiments/<identifier>/short-comments/scenes/<sid>')
def campaign_short_comment_scene(identifier,sid):
    from .campaign_comments import scene_result
    return jsonify(success=True,data=scene_result(campaign_root(),identifier,sid))
