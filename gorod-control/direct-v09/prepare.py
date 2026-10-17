from pathlib import Path
import re,shutil,json
ROOT=Path(__file__).resolve().parents[1];D=ROOT/'direct-v09';ANDROID=ROOT/'android'

def change(s,a,b):
 if a not in s:raise RuntimeError('Patch anchor missing: '+a[:130])
 return s.replace(a,b,1)

def main():
 shutil.copy2(ROOT/'source-lab-v08/water_verified.py',D/'water_verified.py')
 java=ANDROID/'app/src/main/java/ru/citycontrol/shakhty'
 for name in ('WaterNotice.java','DirectClient.java'):shutil.copy2(D/name,java/name)
 grad=ANDROID/'app/build.gradle';s=grad.read_text()
 s=re.sub(r'versionCode \d+','versionCode 9',s)
 s=re.sub(r"versionName '[^']+'","versionName '0.9.0-test'",s)
 s=s.replace("applicationId 'ru.citycontrol.shakhty'","applicationId 'ru.citycontrol.shakhty.beta'")
 grad.write_text(s)
 manifest=ANDROID/'app/src/main/AndroidManifest.xml';s=manifest.read_text().replace('android:label="Город под контролем"','android:label="Город · тест 0.9"');manifest.write_text(s)
 mainfile=java/'MainActivity.java';s=mainfile.read_text()
 s=change(s,'  private WebView web;','  private WebView web;\n  private volatile boolean sourcesRefreshing=false;')
 s=s.replace('CityControlApp/0.4','CityControlApp/0.9')
 s=change(s,'    web = new WebView(this);','    web = new WebView(this);\n    WebView.setWebContentsDebuggingEnabled((getApplicationInfo().flags & android.content.pm.ApplicationInfo.FLAG_DEBUGGABLE)!=0);')
 anchor='      @Override public boolean shouldOverrideUrlLoading(WebView view,WebResourceRequest request){'
 intercept='''      @Override public android.webkit.WebResourceResponse shouldInterceptRequest(WebView view,WebResourceRequest request){
        Uri u=request.getUrl();
        if("https".equals(u.getScheme())&&TRUSTED_HOST.equals(u.getHost())&&u.getPath()!=null&&u.getPath().startsWith(TRUSTED_PATH)){
          String relative=u.getPath().substring(TRUSTED_PATH.length());if(relative.isEmpty())relative="index.html";
          if(!relative.contains("..")&&(relative.equals("index.html")||relative.startsWith("map-v07/"))){
            String type=relative.endsWith(".js")?"application/javascript":relative.endsWith(".css")?"text/css":relative.endsWith(".png")?"image/png":"text/html";
            try{return new android.webkit.WebResourceResponse(type,type.startsWith("image/")?null:"UTF-8",getAssets().open("web/"+relative));}
            catch(Exception ex){return new android.webkit.WebResourceResponse("text/plain","UTF-8",404,"Not Found",java.util.Collections.emptyMap(),new java.io.ByteArrayInputStream(new byte[0]));}
          }
        }
        return super.shouldInterceptRequest(view,request);
      }
'''
 s=change(s,anchor,intercept+anchor)
 anchor='        Uri target=request.getUrl();'
 s=change(s,anchor,anchor+'''
        if("citycontrol".equals(target.getScheme())&&"refresh-sources".equals(target.getHost())){
          if(request.isForMainFrame()&&isTrustedPage(view.getUrl()))startNativeSources();
          return true;
        }
''')
 anchor='  private boolean isTrustedPage(String url) {'
 methods='''  private void deliverFeed(org.json.JSONObject data){
    if(!isTrustedPage(web!=null?web.getUrl():null))return;
    String payload=android.util.Base64.encodeToString(data.toString().getBytes(java.nio.charset.StandardCharsets.UTF_8),android.util.Base64.NO_WRAP);
    web.evaluateJavascript("window.CityControlNativeFeed && window.CityControlNativeFeed(JSON.parse(new TextDecoder().decode(Uint8Array.from(atob('"+payload+"'),c=>c.charCodeAt(0)))));",null);
  }
  private void startNativeSources(){
    if(sourcesRefreshing)return;
    sourcesRefreshing=true;
    org.json.JSONObject cached=DirectClient.cached(getApplicationContext());
    try{cached.put("refreshing",true);}catch(Exception ignored){}
    deliverFeed(cached);
    final android.content.Context app=getApplicationContext();
    new Thread(()->{
      org.json.JSONObject data=DirectClient.refresh(app);
      try{data.put("refreshing",false);}catch(Exception ignored){}
      sourcesRefreshing=false;
      handler.post(()->deliverFeed(data));
    },"CityDirectSources").start();
  }

'''
 s=change(s,anchor,methods+anchor);mainfile.write_text(s)
 service=java/'WaterMonitorJobService.java';s=service.read_text()
 a=s.index('    HttpURLConnection conn=');b=s.index('    if(data.optInt("schema",0)!=2)return;',a)
 s=s[:a]+'    JSONObject data=DirectClient.refresh(getApplicationContext());\n'+s[b:]
 s=change(s,'    boolean powerRostov=false,powerDon=false,powerCity=false,gasCity=false,mchs=false;','    boolean powerRostov=false,powerDon=false,powerCity=false,gasCity=false,mchs=false,powerDirect=false,ursvDevice=false;')
 s=change(s,'      String sourceId=src.optString("id","");','''      long checked=utcMillis(src.optString("checkedAt",data.optString("checkedAt","")));
      if(checked<=0||now-checked>4L*3600000)continue;
      String sourceId=src.optString("id","");
      if(sourceId.equals("power_direct"))powerDirect=true;
      if(sourceId.equals("ursv_device"))ursvDevice=true;''')
 s=s.replace('if(!(waterDirect||city||waterRepost||powerRostov||powerDon||powerCity||gasCity||mchs))return;','if(!(waterDirect||city||waterRepost||powerRostov||powerDon||powerCity||gasCity||mchs||powerDirect||ursvDevice))return;')
 s=change(s,'      if(e==null||!"active".equals(e.optString("status")))continue;','      if(e==null||!"active".equals(e.optString("status"))||e.optBoolean("requiresReview",false))continue;')
 s=change(s,'        if(origin.equals("verified_repost")){','''        if(origin.equals("official_device")){
          if(!ursvDevice||!e.optString("url","").matches("^https://rovodokanal\\\\.ru/emergency-alerts/\\\\d+$"))continue;
        }else if(origin.equals("verified_repost")){''')
 s=change(s,'        if(origin.equals("attributed_repost"))valid=', '''        if(origin.equals("official_site")&&powerDirect&&e.optString("sourceId","").equals("power_direct")&&url.equals("https://donenergo.ru/grafik-otklyucheniy/61/1/"))valid=true;
        if(origin.equals("attributed_repost"))valid=''')
 service.write_text(s)
 # Self-contained UI. Neither a production HTML replacement nor a hidden server-side source shortcut.
 assets=ANDROID/'app/src/main/assets/web';assets.mkdir(parents=True,exist_ok=True)
 shutil.copytree(ROOT/'map-v07',assets/'map-v07',dirs_exist_ok=True,ignore=shutil.ignore_patterns('*.py','*.pyc','__pycache__'))
 (assets/'data').mkdir(exist_ok=True)
 s=(ROOT/'index.html').read_text()
 s=s.replace('КАРТА v0.7','АПК 0.9 · ТЕСТ')
 s=re.sub(r"@import url\('https://fonts.googleapis.com/[^\n]+\n",'',s)
 s=change(s,"const sources = [","const sources = [\n  {id:'ursv_device',icon:'💧',name:'УРСВ · напрямую с телефона',detail:'Результат прямого чтения оригиналов',url:'https://rovodokanal.ru/emergency-alerts/'},\n  {id:'power_direct',icon:'⚡',name:'Донэнерго · прямой официальный график',detail:'Плановые отключения ШМЭС',url:'https://donenergo.ru/grafik-otklyucheniy/61/1/'},")
 s=re.sub(r"^.*\{id:'power_planned'.*\n",'',s,flags=re.M)
 a=s.index('async function checkSources(){');b=s.index('function toggleDemo(){',a)
 replacement=r'''function freshSource(s){
  const age=Date.now()-Date.parse(s?.checkedAt||'');
  return !!s&&s.status==='ok'&&Number.isFinite(age)&&age>=-120000&&age<4*3600000;
}
function ingestFeed(data){
  if(data.schema!==2||!Array.isArray(data.sources)||!Array.isArray(data.events))throw Error('Нет доступной сводки');
  const defaultStamp=data.cloudCheckedAt||data.checkedAt;
  state.checks=data.sources.map(s=>({...s,checkedAt:s.checkedAt||defaultStamp}));
  const by=Object.fromEntries(state.checks.map(s=>[s.id,s]));
  state.checkedAt=data.nativeCheckedAt||data.checkedAt;state.backendConnected=state.checks.some(freshSource);
  state.events=data.events.filter(e=>{
    const url=String(e.url||'');
    if(e.sourceId==='power_direct')return freshSource(by.power_direct)&&e.origin==='official_site'&&url==='https://donenergo.ru/grafik-otklyucheniy/61/1/';
    if(e.sourceId==='ursv_device')return ['ok','partial'].includes(by.ursv_device?.status)&&/^https:\/\/rovodokanal\.ru\/emergency-alerts\/\d+$/.test(url)&&e.origin==='official_device';
    if(e.category==='water')return e.origin==='verified_repost'&&(freshSource(by.repost_rostov)||freshSource(by.repost_don))||e.source==='Администрация города Шахты'&&freshSource(by.city);
    if(e.category==='mchs')return freshSource(by.mchs)&&url.startsWith('https://61.mchs.gov.ru/deyatelnost/press-centr/operativnaya-informaciya/');
    if(e.category==='power')return e.origin==='official_city_post'&&freshSource(by.power_city)||e.origin==='attributed_repost'&&(freshSource(by.power_repost_don)||freshSource(by.power_repost_rostov));
    if(e.category==='gas')return e.origin==='official_city_post'&&freshSource(by.gas_city);
    return false;
  });
  const direct=by.ursv_device;
  $('directStatus').textContent=direct?(direct.status==='ok'?'Оригиналы УРСВ получены. ':'Прямое чтение воды пока не подтверждено. ')+(direct.note||''):'УРСВ: прямая проверка выполняется с телефона. До успешного чтения источник не считается подключённым.';
  $('directTime').textContent=direct?.checkedAt?'Проверка на телефоне: '+fmtTime(direct.checkedAt):'Прямой график света проверяется сервером, МЧС — по официальному RSS.';
  renderSources();renderEvents();
}
window.CityControlNativeFeed=data=>{
  try{ingestFeed(data);}catch(e){$('directStatus').textContent='Нет сохранённой сводки. Ожидается проверка источников.';}
  if(!data.refreshing){state.nativePending=false;state.lastLocalCheck=Date.now();$('checkButton').disabled=false;$('refreshIcon').textContent='↻';}
};
async function checkSources(){
  if(state.demo){toast('Отключите учебный режим для чтения настоящих публикаций');return;}
  if(state.nativePending)return;
  $('checkButton').disabled=true;$('refreshIcon').textContent='…';
  if(/CityControlApp\/0\.9/.test(navigator.userAgent)){
    state.nativePending=true;location.href='citycontrol://refresh-sources';
    setTimeout(()=>{if(state.nativePending){state.nativePending=false;$('checkButton').disabled=false;$('refreshIcon').textContent='↻';toast('Источники отвечают медленно. Нет подтверждения полной проверки.');}},100000);
    return;
  }
  try{const r=await fetch('./direct-v09/feed.json?_='+Date.now(),{cache:'no-store'});if(!r.ok)throw Error('HTTP '+r.status);ingestFeed(await r.json());}
  catch(e){toast('Не удалось обновить сведения. Прямое чтение воды доступно в Android-приложении.');}
  finally{$('checkButton').disabled=false;$('refreshIcon').textContent='↻';}
}
'''
 s=s[:a]+replacement+s[b:]
 # Visible source diagnostics, not a green indicator produced merely by a successful profile HTTP request.
 anchor='<section class="control-card">'
 s=change(s,anchor,'''<section class="control-card" id="directCard"><div class="eyebrow">ПРЯМЫЕ ИСТОЧНИКИ · ТЕСТ 0.9</div><p id="directStatus" style="font-size:12px;line-height:1.6">Проверяются официальный график света, RSS МЧС и прямой доступ к УРСВ с телефона.</p><p class="quiet" id="directTime">Не все службы публикуют полные адресные данные.</p></section>'''+anchor)
 s=change(s,'</style>','''.source-main small{white-space:normal;line-height:1.5;overflow:visible}.sources-grid{align-items:start}#directCard{border-color:#b4dfd4}#directStatus{overflow-wrap:anywhere}</style>''')
 # Treat malformed official house ranges as uncertain rather than claiming exact address exclusion.
 s=change(s,'      streetMatch = true;','      streetMatch = true;\n      if(area.housesUncertain)possibleMatch=true;')
 s=s.replace("state.checks.some(s=>s.status==='stale')?'Последняя доступная публикация водоканала устарела. Приложение не может подтвердить текущую обстановку; проверяйте первоисточник.':'Проверка водоканала недоступна или давно не обновлялась. Нельзя утверждать, что всё спокойно.'","'Не все источники доступны или обновлены. Отсутствие сообщений не подтверждает отсутствие происшествий.'")
 (assets/'index.html').write_text(s)
 cmap=assets/'map-v07/city-map.js';s=cmap.read_text()
 s=s.replace("fetch('./data/map-geometry.json?_='+Date.now()","fetch('https://27andrej1976-afk.github.io/maximum-shakhty-admin/gorod-control/direct-v09/map-geometry.json?_='+Date.now()")
 s=s.replace("field(e.category==='mchs'?'Период начинается':'Начало по объявлению',format(e.start));","field(e.category==='mchs'?'Период начинается':'Начало по объявлению',e.startBasis==='date_only'?'Указана дата; точное время не опубликовано':format(e.start));")
 s=s.replace("field('Источник',sourceText(e));body.append(grid);","field('Источник',sourceText(e));if(e.requiresReview)field('Требуется уточнение','Часть адресов, диапазонов или сроков неоднозначна. Автоматическое уведомление по спорным данным не отправляется.');body.append(grid);")
 s=s.replace("  const links=el('div','cm-detail-links');","  if(e.unmappedAreaText?.length)body.append(el('p','cm-muted','Неоднозначные сведения: '+e.unmappedAreaText.join('; ')));\n  const links=el('div','cm-detail-links');")
 cmap.write_text(s)
 print('PREPARED beta APK: offline UI, unchanged native GPS and city map, direct water status visible')
if __name__=='__main__':main()
