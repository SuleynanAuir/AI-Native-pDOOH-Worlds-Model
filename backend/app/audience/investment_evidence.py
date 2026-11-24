"""Recover matching immutable experiments by exact creative and screen identities."""
from pathlib import Path
from .world import read_json
from .investment import campaign_evidence
from .coverage import supplement


def matches(spec,setup):
    keys=('brand','title','message','topic','source_url')
    if not setup.get('campaign'):return False
    if any(spec.get('campaign',{}).get(k)!=setup['campaign'].get(k) for k in keys):return False
    asset=setup.get('creative')
    # A newly supplied image must never inherit the old text-only experiment.
    expected=spec.get('campaign',{}).get('creative_asset')
    return (asset or {}).get('id')==(expected or {}).get('id')


def resolve(root,project,requested=None,threshold=60):
    setup=project.get('ad_setup',{});candidates=[]
    for path in (Path(root)/'campaign_experiments').glob('*/state.json'):
        try:s=read_json(path)
        except (ValueError,OSError):continue
        if s.get('status')!='completed':continue
        if setup.get('campaign') and not matches(s['spec'],setup):continue
        if not setup.get('campaign') and s['id']!=requested:continue
        candidates.append(s)
    if requested:
        selected=next((s for s in candidates if s['id']==requested),None)
        if not selected:raise ValueError('广告或物料已改变，不能复用旧实验；请执行当前广告态度分析')
        candidates=[selected]
    evidence=campaign_evidence(root,None,threshold);best=None;best_count=0
    ids={f['screen_id'] for f in project['frames']}
    for s in sorted(candidates,key=lambda s:s.get('updated_at',''),reverse=True):
        item=campaign_evidence(root,s['id'],threshold)
        # Same campaign, exact screen ID + coordinate checked again in report().
        sources=[]
        for path in sorted((Path(root)/'planning').glob('*/coverage-'+s['id'])):
            supplement(root,path.parent.name,s['id'],item,threshold)
            sources.append(path.parent.name)
        count=len(ids & set(item['screens']))
        if count>best_count:best=item;best_count=count;best['reused_project_ids']=sources
    if best:evidence=best
    evidence['auto_linked']=bool(best and not requested)
    return evidence
