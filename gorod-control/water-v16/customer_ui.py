"""Apply the approved customer layout to the pinned compact UI; no APK build."""
from pathlib import Path

def replace(src, old, new):
    if old not in src:raise ValueError('Customer layout anchor missing: '+old[:100])
    return src.replace(old,new,1)

def apply(folder):
    folder=Path(folder)
    p=folder/'compact.js';s=p.read_text()
    s=replace(s,' app.append(headline,metrics,address,overview,toolbar,mapCard,notice);', ''' app.append(headline,metrics,address,toolbar,mapCard);
 const report=left.querySelector('#reportIssueButton')?.closest('section');''')
    s=replace(s,' move(heading,local);move(filters,local);move(eventList,local);',''' move(heading,local);move(filters,local);move(eventList,local);
 app.append(overview,notice);
 if(report)app.append(report);''')
    s=replace(s," const radius=address.querySelector('.radius');",''' services.hidden=true;
 settings.hidden=true;
 const gps=$('geoButton');
 if(gps){gps.textContent='◎ Определить моё местоположение';gps.setAttribute('aria-label','Определить моё местоположение');}
 const radius=address.querySelector('.radius');''')
    s=replace(s," navItem('☷','Ещё',()=>showSection(services,services));", " navItem('✎','Обращение',()=>report?.scrollIntoView({behavior:'smooth',block:'start'}));")
    p.write_text(s)
    css=folder/'compact.css'
    css.write_text(css.read_text()+'''
/* Customer view: DOM order controls layout at every viewport width. */
.main.compact-main>*{order:0!important}
#compactSourcesFold[hidden],#compactSettingsFold[hidden]{display:none!important}
.compact-main .overview-card.clear{background:#fff5d1;border:1px solid #d3ad28;color:#352c1c}
.compact-main .overview-card.clear .overview-top,.compact-main .overview-card.clear .radar-icon,
.compact-main .overview-card.clear .status-text{color:#735313}
.compact-main .overview-card.clear .radar-icon{background:#f9e5a0}
.compact-main .overview-card.clear h2{color:#352c1c}
.compact-main .overview-card.clear p,.compact-main .overview-card.clear .overview-foot{color:#655638}
.compact-main .overview-card.clear .overview-foot{border-color:#e4ce81}
''')

if __name__=='__main__':apply('gorod-control/compact-v11')
