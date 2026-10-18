"""Generate a separately accessible Yandex Maps beta; do not touch running app."""
from pathlib import Path
import re
ROOT=Path(__file__).resolve().parents[1]
ORIGINAL=ROOT/'index.html'
DEST=ROOT/'yandex-v1'/'index.html'
def build():
    html=ORIGINAL.read_text(encoding='utf-8')
    assert 'function makeMap(){window.CityMapV07.start();}' in html
    assert '<script src="./map-v07/city-map.js?v=0.7.0"></script>' in html
    html=html.replace('<head>','<head>\n  <base href="../">',1)
    html=html.replace('</title>','</title>\n  <link rel="stylesheet" href="./yandex-v1/yandex.css?v=1.0.0">',1)
    html=html.replace('<script src="./map-v07/city-map.js?v=0.7.0"></script>','<script src="./map-v07/city-map.js?v=0.7.0"></script>\n<script src="./yandex-v1/yandex-bridge.js?v=1.0.0"></script>',1)
    html=html.replace('function makeMap(){window.CityMapV07.start();}','function makeMap(){window.CityYandexV1.startWithFallback(()=>window.CityMapV07.start());}',1)
    html=html.replace('КАРТА v0.7','ЯНДЕКС · БЕТА',1)
    assert 'CityYandexV1.startWithFallback' in html
    assert 'function makeMap(){window.CityMapV07.start();}' not in html
    DEST.write_text(html,encoding='utf-8')
    print('Prepared isolated Yandex preview', DEST, len(html))
if __name__=='__main__':build()
