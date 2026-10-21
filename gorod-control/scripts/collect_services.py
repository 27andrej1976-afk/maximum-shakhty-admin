#!/usr/bin/env python3
"""Augment water.json with monitored, separately verified power/MCHS/gas source data.

Reads public feeds only. Never stores user location. A live HTTP response is NOT
proof that all local utility outages are published by that service.
"""
import json
import os
import re
import ssl
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.request import Request,urlopen
from xml.etree import ElementTree as ET
from service_events import mchs_posts, power_posts
from city_utility import collect_city
from rss_water import RSS_URLS
from public_rss import fetch as fetch_rss

OUTPUT=Path(__file__).resolve().parents[1]/'data'/'water.json'
MCHS='https://61.mchs.gov.ru/deyatelnost/press-centr/operativnaya-informaciya/rss'
GAS='https://www.rostovoblgaz.ru/press-center/news/'
GAS_CONTACTS='https://www.rostovoblgaz.ru/compani/gro_shakhty/kontakty/'
POWER_PLAN='https://donenergo.ru/grafik-otklyucheniy/61/1/'
USER_AGENT='Mozilla/5.0 (compatible; ShakhtyCityControl/0.6; official-source-monitor)'
UTC=timezone.utc

def fetch(url,timeout=15,maxbytes=6_000_000):
    req=Request(url,headers={'User-Agent':USER_AGENT,'Accept':'application/xml,text/xml,text/html,*/*'})
    with urlopen(req,timeout=timeout) as resp:
        if resp.status!=200:raise RuntimeError('HTTP '+str(resp.status))
        return resp.read(maxbytes)

def source(id,status,url,**fields):
    return {'id':id,'status':status,'url':url,**fields}

def collect_power(now):
    results=[];states=[];accepted=0
    for index,url in enumerate(RSS_URLS):
        id='power_repost_rostov' if index==0 else 'power_repost_don'
        domain=url.split('/')[2]
        try:
            raw=fetch_rss(url,timeout=16)
            items=ET.fromstring(raw).findall('.//item')
            parsed=power_posts(raw,domain,now)
            accepted+=len(parsed)
            results.extend(parsed)
            most_recent=max((datetime.fromisoformat(e['publishedAt']) for e in parsed),default=None)
            states.append(source(id,'ok' if most_recent and now-most_recent<timedelta(days=3) else 'partial',url,
                readStatus="ok",coverage="partial",posts=len(items),matchingPosts=len(parsed),
                lastPostAt=most_recent.isoformat() if most_recent else None,
                note='Перепечатки сообщений Донэнерго через MAX / администрацию; не полная лента отключений'))
            print('POWER',id,'RSS items',len(items),'Shakhty verified notices',len(parsed))
        except Exception as e:
            states.append(source(id,'error',url,posts=0,note='Нет доступа к RSS: '+str(e)[:120]))
            print('POWER ERROR',id,str(e)[:110])
    # Deduplicate the same incident syndicated by both mirrors.
    by_id={}
    for event in results:
        existing=by_id.get(event['id'])
        if not existing or len(event['description'])>len(existing['description']):by_id[event['id']]=event
    return list(by_id.values()),states

def collect_mchs(now):
    try:
        raw=fetch_rss(MCHS,timeout=18)
        root=ET.fromstring(raw)
        items=root.findall('.//item')
        last=None
        for it in items:
            try:
                parsed=parsedate_to_datetime(it.findtext('pubDate',''))
                if parsed.tzinfo is None:parsed=parsed.replace(tzinfo=timezone(timedelta(hours=3)))
                if last is None or parsed>last:last=parsed
            except Exception:continue
        events=mchs_posts(raw,now)
        fresh=last is not None and timedelta(minutes=-30)<now-last<timedelta(days=7)
        status='ok' if fresh else 'stale'
        print('MCHS official RSS',len(items),'Shakhty/region scoped events',len(events))
        return events,source('mchs',status,MCHS,posts=len(items),matchingPosts=len(events),
            lastPostAt=last.isoformat() if last else None,note='Официальный RSS. Только актуальные предупреждения, прямо относящиеся к Шахтам')
    except Exception as exc:
        print('MCHS ERROR',str(exc)[:160])
        return [],source('mchs','error',MCHS,posts=0,note='Не удалось получить официальный RSS МЧС: '+str(exc)[:120])

def collect_gas(now):
    """Explicitly partial until a dated, machine-readable address feed is verified."""
    try:
        page=fetch(GAS,timeout=12,maxbytes=900_000).decode('utf-8','replace')
        # The gas company homepage/press page does not provide reliable per-house outage reports.
        # Never turn corporate news or vague place mentions into gas disruption alerts.
        available=bool(re.search(r'Газпром|газораспределени',page,re.I))
        if not available:raise RuntimeError('Official press-page signature absent')
        return source('gas','partial',GAS,readStatus='ok',posts=0,lastPostAt=None,
           note='Официальный сайт доступен, но адресная лента отключений газа не подтверждена; автоматических тревог по газу пока нет')
    except Exception as exc:
        return source('gas','error',GAS,posts=0,note='Нет проверяемой ленты газа: '+str(exc)[:120])

def collect_power_planned():
    try:
        body=fetch(POWER_PLAN,timeout=9,maxbytes=100000).decode('utf-8','replace')
        if not re.search(r'отключени|Донэнерго',body,re.I):raise RuntimeError('No planned outage text')
        return source('power_planned','partial',POWER_PLAN,posts=0,
            note='Страница читается, но таблица отключений по улицам пока не разобрана')
    except Exception as e:
        return source('power_planned','error',POWER_PLAN,posts=0,
            note='Автоматическое чтение графика не подтверждено: '+str(e)[:90])

def main():
    now=datetime.now(UTC)
    data=json.loads(OUTPUT.read_text(encoding='utf-8'))
    power,power_states=collect_power(now)
    mchs,mchs_state=collect_mchs(now)
    gas_state=collect_gas(now)
    plan_state=collect_power_planned()
    municipal,municipal_states=collect_city(now)
    # First collector restores only verified water info. Other categories are rebuilt every run.
    events=data.get('events',[])
    original_water=[x for x in events if x.get('category')=='water']
    known=data.get('serviceArchive',[])
    fresh=power+mchs+municipal
    by_id={x['id']:x for x in fresh if x.get('id')}
    for item in known:
        if item.get('id') in by_id or item.get('category') not in ('power','mchs','gas'):continue
        try:
            p=datetime.fromisoformat(item['publishedAt'])
            if not timedelta(minutes=-30)<now-p<timedelta(hours=48):continue
            end=datetime.fromisoformat(item['end']) if item.get('end') else None
            if end and end<now-timedelta(hours=24):continue
            copy=dict(item)
            copy['status']='unconfirmed'
            copy['description']=item.get('description','')[:450]
            by_id[copy['id']]=copy
        except (KeyError,TypeError,ValueError):pass
    archived=sorted(by_id.values(),key=lambda x:x.get('publishedAt',''),reverse=True)[:90]
    data['serviceArchive']=archived
    data['events']=original_water+archived
    data['sources']=[s for s in data.get('sources',[]) if s.get('id') not in
       ('mchs','gas','power_planned','power_repost_rostov','power_repost_don','power_city','gas_city')]+power_states+municipal_states+[plan_state,gas_state,mchs_state]
    data['checkedAt']=now.isoformat()
    data['schema']=2
    OUTPUT.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('FINAL CITY CONTROL',len(original_water),'water',len(power),'new power',len(mchs),'new MCHS',
          'municipal notices',len(municipal),'saved alerts',len(data['events']),'statuses',[(s['id'],s['status']) for s in data['sources']])
if __name__=='__main__':main()
