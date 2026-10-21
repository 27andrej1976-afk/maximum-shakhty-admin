"""Keep the existing report layouts; install the water update as separate apps."""
from pathlib import Path
import os
if os.environ.get('CITY_VARIANT')!='compact':
    raise SystemExit('Only the compact app is supported')
r=Path('gorod-control/report-apks-v15')
for name in ('prepare_variant.py','android_test.py'):
    p=r/name;s=p.read_text().replace('normalreport','normalwater').replace('compactreport','compactwater')
    s=s.replace('1.2.0-report-','1.6.0-water-').replace('versionCode 15','versionCode 19').replace('versionCode 16','versionCode 22')
    s=s.replace('Город · классика+','Город · вода').replace('Город · компакт+','Город · вода компакт')
    if name=='android_test.py':
        extra='''
check(evaluate("document.querySelector('#sourcesGrid').textContent.includes('КВУ')"),'KVU source included in installed app')
evaluate("window.releaseTestFeed=window.CityControlNativeFeed;window.CityControlNativeFeed=()=>{};true")
fixture={
 'schema':2,'checkedAt':__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),
 'sources':[{'id':'water_kvu','status':'ok'},{'id':'repost_don','status':'ok'}],
 'events':[{'id':'water-test-secondary','category':'water','kind':'emergency','status':'active',
 'origin':'media_report','sourceId':'water_kvu','source':'КВУ — публикация СМИ',
 'url':'https://kvu.su/utilities/test.html','title':'Проверка источника','description':'Тест',
 'affected':[{'street':'ул Тестовая','houses':[]}]}]}
evaluate('window.releaseTestFeed('+json.dumps(fixture,ensure_ascii=False)+')')
check(evaluate("CityMapV07.inspect().allIds.includes('water-test-secondary')"),'Installed app accepts fresh secondary water source')
fixture['sources'][0]['status']='error'
evaluate('window.releaseTestFeed('+json.dumps(fixture,ensure_ascii=False)+')')
check(evaluate("!CityMapV07.inspect().allIds.includes('water-test-secondary')"),'Failed source cannot validate secondary event')
evaluate("window.CityControlNativeFeed=window.releaseTestFeed;true")
'''
        assert 'ws.close()' in s;s=s.replace('ws.close()',extra+"\nexec(Path('gorod-control/water-v16/test_android_power_retention.py').read_text())\nexec(Path('gorod-control/water-v16/test_android_pan.py').read_text())\nws.close()")
    p.write_text(s)
# The report button can initialize before compact's window-level DOMContentLoaded
# handler. Move its existing section before compact removes the old left panel.
compact=Path('gorod-control/compact-v11/compact.js')
if compact.exists():
    s=compact.read_text()
    anchor=' app.append(headline,metrics,address,overview,toolbar,mapCard,notice);'
    assert anchor in s
    s=s.replace(anchor,anchor+"\n const report=left.querySelector('#reportIssueButton')?.closest('section');\n if(report)toolbar.insertAdjacentElement('afterend',report);",1)
    compact.write_text(s)

# Fail before building if the shared MapLibre v5 pan correction is lost again.
bridge=Path('gorod-control/light-v10/vendor/leaflet-maplibre-gl.js').read_text()
assert 'gl.transform.apply(tr)' in bridge and 'gl.resize()' in bridge, 'Map pan synchronization fix missing'
