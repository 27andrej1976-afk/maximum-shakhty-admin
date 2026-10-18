"""Create preview or embedded Android compact UI preserving the tested application and its data logic."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parent
def build(source,dest,preview=False):
    source,dest=Path(source),Path(dest)
    original=source.read_text(encoding='utf-8')
    css=(ROOT/'compact.css').read_text(encoding='utf-8')
    js=(ROOT/'compact.js').read_text(encoding='utf-8')
    assert 'function makeMap(){window.CityMapV07.start();}' in original
    assert 'id="eventList"' in original
    assert 'id="sourcesGrid"' in original
    assert 'city-map.js?' in original
    assert '<script' not in js.lower() and '</style' not in css.lower()
    original=original.replace('</head>', '<style id="compactV11Style">\n'+css+'\n</style>\n</head>',1)
    original=original.replace('</body>', '<script id="compactV11Logic">\n'+js+'\n</script>\n</body>',1)
    original=original.replace('КАРТА · СВЕТЛАЯ','КОМПАКТ · ТЕСТ',1)
    original=original.replace('<title>Город под контролем • Шахты</title>','<title>Город под контролем — компактная тестовая версия</title>',1)
    if preview:
        original=original.replace('<head>','<head>\n<base href="../">',1)
    assert original.count('id="compactV11Style"')==1 and original.count('id="compactV11Logic"')==1
    assert 'data/water.json' in original and 'CityControlNativeGPSResult' in original
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(original,encoding='utf-8')
    print('COMPACT READY',dest,'preview='+str(preview),'bytes='+str(len(original)),flush=True)
if __name__=='__main__':
    if len(sys.argv) not in (3,4):raise SystemExit('usage: build_compact.py INPUT OUTPUT [--preview]')
    build(sys.argv[1],sys.argv[2],len(sys.argv)==4 and sys.argv[3]=='--preview')
