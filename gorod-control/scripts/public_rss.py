"""Bounded public RSS fetch with one retry for transient network failures."""
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
import xml.etree.ElementTree as ET
LIMIT=7_000_000

def fetch(url,timeout=17):
    for attempt in range(2):
        try:
            request=Request(url,headers={'User-Agent':'Mozilla/5.0 (compatible; CityControlShakhty/1.3; public RSS)'})
            with urlopen(request,timeout=timeout) as response:raw=response.read(LIMIT+1)
            if len(raw)>LIMIT:raise ValueError('RSS exceeds size limit')
            root=ET.fromstring(raw)
            if root.tag!='rss' or root.find('channel') is None:raise ValueError('Expected RSS channel')
            return raw
        except HTTPError as exc:
            if attempt or (exc.code!=429 and exc.code<500):raise
        except (URLError,TimeoutError):
            if attempt:raise
