"""Keep verified power notices through end + 36h, never extend on refresh/errors."""
from copy import deepcopy
from datetime import datetime, timedelta
from urllib.parse import urlparse

def stamp(value):
    try:
        d=datetime.fromisoformat(value.replace('Z','+00:00'))
        return d if d.tzinfo else None
    except (ValueError,TypeError,AttributeError):return None

def source_id(e):
    host=urlparse(e.get('url','')).hostname
    origin=e.get('origin')
    if origin=='official_site' and e.get('sourceId')=='power_direct' and e.get('url')=='https://donenergo.ru/grafik-otklyucheniy/61/1/':return 'power_direct'
    if origin=='official_city_post' and host=='t.me' and urlparse(e.get('url','')).path.startswith('/admshakhty/'):return 'power_city'
    if origin=='attributed_repost':return {'news-don.ru':'power_repost_don','newsrostov.ru':'power_repost_rostov'}.get(host)
    if origin=='official_max' and not e.get('requiresReview'):
        expected={'max_city':'https://max.ru/shakhtygorod','max_power':'https://max.ru/id6163089292_biz'}
        sid=e.get('sourceId')
        if sid in expected and e.get('url')==expected[sid]:return sid
    return None

def deadline(e):
    anchor=next((d for k in ('end','start','publishedAt','observedAt') if (d:=stamp(e.get(k)))),None)
    return anchor+timedelta(hours=36) if anchor else None

def areas(e):
    return sorted((a.get('street','').lower().strip(),tuple(sorted(a.get('houses') or []))) for a in e.get('affected',[]))

def merge(current,previous,sources,now):
    states={s['id']:s for s in sources}
    by={e['id']:deepcopy(e) for e in previous if e.get('id') and e.get('category')=='power' and source_id(e)}
    fresh_ids=set()
    for e in current:
        sid=source_id(e)
        if e.get('category')!='power' or not sid or not e.get('id'):continue
        s=states.get(sid,{})
        if not (s.get('status')=='ok' or s.get('readStatus')=='ok'):continue
        if by.get(e['id'],{}).get('status') in ('resolved','cancelled','canceled') and e.get('status') not in ('resolved','cancelled','canceled'):continue
        item=deepcopy(e);item['lastConfirmedAt']=s.get('checkedAt') or now.isoformat()
        by[e['id']]=item;fresh_ids.add(e['id'])
    resolutions=[e for e in by.values() if e.get('status')=='resolved']
    out=[]
    for e in by.values():
        until=deadline(e)
        if not until or now>=until:continue
        # Only exact address/house coverage and a newer explicit restoration notice.
        start=stamp(e.get('start'))
        for r in resolutions:
            resolved=stamp(r.get('publishedAt'))
            if e.get('status')!='resolved' and areas(e) and areas(e)==areas(r) and start and resolved and start<=resolved<=now:
                e['status']='resolved';e['resolvedAt']=resolved.isoformat();e['resolutionUrl']=r['url']
        e['retainUntil']=until.isoformat()
        e['lastConfirmedAt']=e.get('lastConfirmedAt') or e.get('observedAt') or e.get('publishedAt')
        e['retained']=e['id'] not in fresh_ids
        if e.get('status') not in ('resolved','cancelled','canceled'):
            ended=stamp(e.get('end'))
            if e['retained'] or (ended and ended<now):e['status']='unconfirmed'
        out.append(e)
    return out
