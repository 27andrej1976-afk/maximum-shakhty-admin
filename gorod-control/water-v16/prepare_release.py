"""Keep the existing report layouts; install the water update as separate apps."""
from pathlib import Path
import os
if os.environ.get('CITY_VARIANT')!='compact':
    raise SystemExit('Only the compact app is supported')
r=Path('gorod-control/report-apks-v15')
for name in ('prepare_variant.py','android_test.py'):
    p=r/name;s=p.read_text().replace('normalreport','normalwater').replace('compactreport','compactwater')
    s=s.replace('1.2.0-report-','1.9.0-water-').replace('versionCode 15','versionCode 19').replace('versionCode 16','versionCode 25')
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
 'end':(__import__('datetime').datetime.now(__import__('datetime').timezone.utc)+__import__('datetime').timedelta(hours=1)).isoformat(),
 'url':'https://kvu.su/utilities/test.html','title':'Проверка источника','description':'Тест',
 'affected':[{'street':'ул Тестовая','houses':[]}]}]}
evaluate('window.releaseTestFeed('+json.dumps(fixture,ensure_ascii=False)+')')
check(evaluate("CityMapV07.inspect().allIds.includes('water-test-secondary')"),'Installed app accepts fresh secondary water source')
fixture['sources'][0]['status']='error'
evaluate('window.releaseTestFeed('+json.dumps(fixture,ensure_ascii=False)+')')
check(evaluate("!CityMapV07.inspect().allIds.includes('water-test-secondary')"),'Failed source cannot validate secondary event')
evaluate("window.CityControlNativeFeed=window.releaseTestFeed;true")
'''
        extra+='\nevaluate("window.scrollTo({top:0,behavior:\'instant\'});true")\ncheck(evaluate("document.querySelector(\'.compact-metrics\').compareDocumentPosition(document.querySelector(\'#geoButton\'))&Node.DOCUMENT_POSITION_FOLLOWING"),\'GPS follows counters\')\ncheck(evaluate("document.querySelector(\'#geoButton\').getBoundingClientRect().bottom<innerHeight"),\'GPS visible without scrolling\')\ncheck(evaluate("document.querySelector(\'#sourcesGrid\').textContent.includes(\'MAX · УРСВ\')"),\'URSV MAX source registered\')\ncheck(evaluate("getComputedStyle(document.querySelector(\'#compactSourcesFold\')).display===\'none\'"),\'Source diagnostics hidden from customer view\')\ncheck(evaluate("getComputedStyle(document.querySelector(\'#compactSettingsFold\')).display===\'none\'"),\'Extra settings hidden from customer view\')\ncheck(evaluate("document.querySelector(\'.map-card\').compareDocumentPosition(document.querySelector(\'#reportIssueButton\'))&Node.DOCUMENT_POSITION_FOLLOWING"),\'Complaint button follows city map\')\ncheck(evaluate("!!document.querySelector(\'.notification-card\') && getComputedStyle(document.querySelector(\'.notification-card\')).display!==\'none\'"),\'Advance warnings block preserved\')\n'
        assert 'ws.close()' in s;s=s.replace('ws.close()',extra+"\nexec(Path('gorod-control/water-v16/test_android_power_retention.py').read_text())\nexec(Path('gorod-control/water-v16/test_android_pan.py').read_text())\nexec(Path('gorod-control/water-v16/test_android_zoom.py').read_text())\nexec(Path('gorod-control/water-v16/test_android_fallback.py').read_text())\nws.close()")
    p.write_text(s)
# Apply the agreed customer screen to the recovered compact UI.
import runpy
runpy.run_path('gorod-control/water-v16/customer_ui.py',run_name='__main__')

# Fail before building if the shared MapLibre v5 pan correction is lost again.
bridge=Path('gorod-control/light-v10/vendor/leaflet-maplibre-gl.js').read_text()
assert 'gl.transform.apply(tr)' in bridge and 'gl.resize()' in bridge, 'Map pan synchronization fix missing'
