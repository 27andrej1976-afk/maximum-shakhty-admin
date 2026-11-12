"""Import current GAR objects/administrative parents from 1C's public GAR mirror.

Input XML is decoded from Fast Infoset by the standard Eclipse implementation,
not scraped address guesses. One UUID/name may occur in multiple settlements:
parent hierarchy is mandatory; never match a street globally by name.
"""
import argparse
import base64
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import uuid
import xml.etree.ElementTree as E

LOCALITIES = {'г.', 'п.', 'с.', 'х.', 'ст-ца', 'сл.', 'ст.', 'рзд.', 'рп.', 'д.'}


def guid(value):
    return str(uuid.UUID(bytes=base64.b64decode(value, validate=True)))


def convert(objects_xml, parents_xml):
    root = E.parse(objects_xml).getroot()
    parents = E.parse(parents_xml).getroot()
    if root.get('Region') != '61' or parents.get('Region') != '61' or root.get('Version') != parents.get('Version'):
        raise ValueError('Wrong region or mixed GAR versions')
    objects = {n.get('OBJECTGUID'): dict(n.attrib) for n in root}
    links = {n.get('OBJECTGUID'): n.get('PARENTOBJECTGUID') for n in parents}
    cities = {k:v for k,v in objects.items() if v.get('LEVEL') in {'5','6'} and v.get('TYPENAME') in LOCALITIES}
    names = Counter(v['NAME'] for v in cities.values())
    localities = []
    for key, obj in cities.items():
        ancestors, cur = [], key
        for _ in range(12):
            cur = links.get(cur)
            if not cur or cur not in objects: break
            a = objects[cur]
            if a.get('LEVEL') in {'3','4'}: ancestors.append(a['NAME'])
        localities.append({'id':guid(key),'name':obj['NAME'],'type':obj['TYPENAME'],
            'label':obj['NAME']+(', '+', '.join(ancestors) if names[obj['NAME']]>1 else ''),
            'districts':ancestors,'verified':True,'verification':'GAR current-object and administrative hierarchy'})
    streets=[]
    for key,obj in objects.items():
        if obj.get('LEVEL')!='8':continue
        cur=key;seen=set()
        for _ in range(16):
            cur=links.get(cur)
            if not cur or cur in seen:break
            if cur in cities:
                streets.append({'id':guid(key),'municipalityId':guid(cur),
                                'name':obj['NAME'],'type':obj['TYPENAME']})
                break
            seen.add(cur)
    return {'regionId':'RU-ROS','version':root.get('Version'),'updatedAt':root.get('UpdateDate'),
        'sourceUrl':'https://its.1c.ru/download/fias/downloadgar?id=61',
        'sourceNote':'GAR FNS current objects redistributed by 1C; UUID decoded from 16-byte base64',
        'municipalities':sorted(localities,key=lambda n:(n['name'],n['id'])), 'streets':streets}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--objects',required=True);p.add_argument('--parents',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();data=convert(a.objects,a.parents)
    raw=json.dumps(data,ensure_ascii=False,separators=(',',':')).encode()
    with open(a.output,'wb') as f:f.write(gzip.compress(raw,mtime=0))
    print(json.dumps({'version':data['version'],'municipalities':len(data['municipalities']),
        'streets':len(data['streets']),'sha256':hashlib.sha256(raw).hexdigest()}))
