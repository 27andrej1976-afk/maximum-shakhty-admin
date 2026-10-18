"""Prepare and version one independent report-enabled Android app from the current code."""
import os,re,shutil,subprocess
from pathlib import Path
variant=os.environ['CITY_VARIANT']
assert variant in ('normal','compact')
app=Path('gorod-control/android/app')
assets=app/'src/main/assets/web'
vendor=Path('gorod-control/light-v10/vendor')
assert (vendor/'maplibre-gl.js').stat().st_size>500000
shutil.copytree(vendor,assets/'light-v10/vendor',dirs_exist_ok=True)
native=app/'src/main/java/ru/citycontrol/shakhty/MainActivity.java'
s=native.read_text()
needle='relative.equals("index.html")||relative.startsWith("map-v07/")'
assert needle in s
native.write_text(s.replace(needle,needle+'||relative.startsWith("light-v10/vendor/")'))
if variant=='compact':
 subprocess.run(['python','gorod-control/compact-v11/build_compact.py',str(assets/'index.html'),str(assets/'index.html')],check=True)
subprocess.run(['python','gorod-control/report-apks-v15/install_reports.py',str(assets/'index.html')],check=True)
dest='ru.citycontrol.shakhty.'+('normalreport' if variant=='normal' else 'compactreport')
name='1.2.0-report-normal' if variant=='normal' else '1.2.0-report-compact'
label='Город · классика+' if variant=='normal' else 'Город · компакт+'
grad=app/'build.gradle'
g=grad.read_text()
assert "applicationId 'ru.citycontrol.shakhty.beta'" in g
g=g.replace("applicationId 'ru.citycontrol.shakhty.beta'",f"applicationId '{dest}'")
g=re.sub(r'versionCode \d+','versionCode 15' if variant=='normal' else 'versionCode 16',g)
g=re.sub(r"versionName '[^']+'",f"versionName '{name}'",g)
grad.write_text(g)
manifest=app/'src/main/AndroidManifest.xml'
m=manifest.read_text()
assert 'android:label="Город · тест 0.9"' in m
manifest.write_text(m.replace('android:label="Город · тест 0.9"',f'android:label="{label}"'))
html=(assets/'index.html').read_text()
assert 'civicReportButtonLogic' in html and 'CityControlNativeFeed' in html
assert 'CityControlNativeGPSResult' in html
assert 'removeCountryFlagSymbols' in (assets/'map-v07/city-map.js').read_text()
print('READY',variant,'PACKAGE',dest,'no upstream UI modified; original native sources preserved')
