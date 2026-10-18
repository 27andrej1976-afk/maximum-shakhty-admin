"""Inject the approved official-submission button into a copy of City Control.
Never modify production web files or an installed APK.
"""
from pathlib import Path
import sys
APP_URL="https://27andrej1976-afk.github.io/maximum-shakhty-admin/gorod-control/official-intake-v14/"
STYLE=r"""
.report-civic-cta{margin:8px 0 10px;background:#fff;border:1px solid #cde5e0;border-radius:15px;
  padding:12px 13px;display:flex;align-items:center;gap:10px;box-shadow:0 4px 14px #0b2b3620}
.report-civic-cta .report-civic-icon{display:grid;place-items:center;flex:none;width:38px;height:38px;
  background:#e6f8f1;color:#09846a;font-size:23px;border-radius:12px}
.report-civic-body{display:grid;gap:3px;flex:1;min-width:0}
.report-civic-body strong{color:#172d43;font-size:12px;font-weight:800}
.report-civic-body small{color:#647f92;font-size:9px;line-height:1.45}
.report-civic-cta a{display:inline-flex;align-items:center;justify-content:center;flex:none;
  padding:11px 12px;background:#0f987a;color:white!important;text-decoration:none;border-radius:10px;font-size:11px;font-weight:800}
@media(max-width:390px){.report-civic-cta{gap:7px;padding:10px}.report-civic-cta a{padding:10px 8px;font-size:10px}}
"""
SCRIPT=r"""
(function(){
'use strict';
function install(){
 if(document.querySelector('#reportIssueButton'))return;
 const toolbar=document.querySelector('.toolbar');
 if(!toolbar)return;
 const section=document.createElement('section');section.className='report-civic-cta';
 section.setAttribute('aria-label','Обращение в администрацию города Шахты');
 const picture=document.createElement('span');picture.className='report-civic-icon';picture.textContent='✎';
 const info=document.createElement('span');info.className='report-civic-body';
 const heading=document.createElement('strong');heading.textContent='Сообщить о проблеме';
 const subtitle=document.createElement('small');subtitle.textContent='Фото, адрес, описание → официальная форма администрации через Госуслуги';
 info.append(heading,subtitle);
 const a=document.createElement('a');a.id='reportIssueButton';a.href='__APP_URL__';
 a.textContent='Сообщить ↗';a.setAttribute('aria-label','Подготовить обращение для администрации города Шахты');
 section.append(picture,info,a);
 toolbar.insertAdjacentElement('afterend',section);
}
// Compact reorganizes the DOM on startup; attach again if it moved the toolbar.
function ready(){
 install();
 setTimeout(install,120);
 setTimeout(install,750);
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',ready);
else ready();
})();
""".replace("__APP_URL__",APP_URL)
def install(path):
 path=Path(path)
 src=path.read_text(encoding='utf-8')
 assert '<head>' in src and '</body>' in src
 assert 'CityControlNativeGPSResult' in src and 'CityMapV07' in src
 assert 'id="reportIssueButton"' not in src and 'report-civic-cta' not in src
 src=src.replace('</head>','<style id="civicReportButtonStyle">\n'+STYLE+'\n</style></head>',1)
 src=src.replace('</body>','<script id="civicReportButtonLogic">\n'+SCRIPT+'\n</script>\n</body>',1)
 assert APP_URL in src
 path.write_text(src,encoding='utf-8')
 print('Reports navigation integrated in',path,'without modifying operational logic.')
if __name__=='__main__':
 if len(sys.argv)!=2:raise SystemExit('usage: install_reports.py HTMLFILE')
 install(sys.argv[1])
