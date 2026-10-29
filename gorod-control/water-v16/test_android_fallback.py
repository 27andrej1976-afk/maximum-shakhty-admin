"""Force a real installed WebView WebGL failure before app scripts, then exercise controls.
Executed by the existing emulator harness with ws/evaluate/check/seq available.
No phone installation or real notices; synthetic fixture lives only in emulator memory.
"""
def cdp(method,params=None):
    global seq
    seq+=1;identity=seq
    ws.send(json.dumps({'id':identity,'method':method,'params':params or {}}))
    for _ in range(250):
        message=json.loads(ws.recv())
        if message.get('id')==identity:
            if message.get('error'):raise RuntimeError(str(message['error']))
            return message.get('result',{})
    raise TimeoutError(method)
cdp('Page.enable')
script=cdp('Page.addScriptToEvaluateOnNewDocument',{'source':'''window.__fallbackErrors=[];addEventListener('error',e=>window.__fallbackErrors.push(e.message));
const originalGetContext=HTMLCanvasElement.prototype.getContext;
HTMLCanvasElement.prototype.getContext=function(kind,...args){if(String(kind).includes('webgl'))return null;return originalGetContext.call(this,kind,...args);};'''})
cdp('Page.reload',{'ignoreCache':True})
for _ in range(35):
    try:
        if evaluate("!!window.CityMapV07 && !!document.querySelector('#cityAllButton') && document.querySelector('#mapStyleInfo').textContent==='Резервная карта'"):break
    except Exception:pass
    time.sleep(1)
else:raise AssertionError('Installed app failed to recover from unavailable WebGL')
check(evaluate("document.createElement('canvas').getContext('webgl2')===null"),'Installed WebView WebGL really unavailable')
check(evaluate("document.querySelectorAll('.leaflet-gl-layer').length===0"),'Failed vector layer removed in installed APK')
check(evaluate("document.querySelectorAll('.leaflet-control-zoom').length===1"),'Raster fallback finishes installed map setup')
evaluate("document.querySelector('#addressButton').click();true")
check(evaluate("document.querySelector('#addressDialog').open"),'Manual address remains operational after vector failure')
evaluate("document.querySelector('#addressDialog button[value=cancel]').click();true")
check(not evaluate("document.querySelector('#addressDialog').open"),'Manual address cancellation works on fallback')
# Exercise native refresh dispatch while blocking only incoming test-racing callbacks.
evaluate("window.fallbackFeed=window.CityControlNativeFeed;window.CityControlNativeFeed=()=>{};true")
now=__import__('datetime').datetime.now(__import__('datetime').timezone.utc)
end=now+__import__('datetime').timedelta(hours=1)
event={'id':'android-fallback-water','category':'water','kind':'emergency','status':'active','origin':'media_report','sourceId':'water_kvu','url':'https://kvu.su/utilities/test-only.html','title':'ТЕСТ резервной карты','start':now.isoformat(),'end':end.isoformat(),'point':{'lat':47.72,'lon':40.23},'affected':[]}
fixture={'schema':2,'checkedAt':now.isoformat(),'sources':[{'id':'water_kvu','status':'ok','checkedAt':now.isoformat()}],'events':[event]}
evaluate('fallbackFeed('+json.dumps(fixture,ensure_ascii=False)+')')
evaluate("document.querySelector('#checkButton').click();true")
check(evaluate("document.querySelector('#checkButton').disabled"),'Refresh handler remains wired after installed vector failure')
evaluate('fallbackFeed('+json.dumps(fixture,ensure_ascii=False)+')')
check(not evaluate("document.querySelector('#checkButton').disabled"),'Native refresh callback restores button after fallback')
evaluate("document.querySelector('#cityAllButton').click();true")
check(evaluate("CityMapV07.inspect().mode==='city' && document.querySelectorAll('.cm-marker').length===1"),'Accepted water marker visible on installed fallback map')
for zoom in [12,14,17,13]:
    evaluate(f"CityMapV07.getMap().setZoom({zoom},{{animate:false}});CityMapV07.getMap().panBy([30,-20],{{animate:false}});true")
    check(evaluate("CityMapV07.inspect().mode==='city' && document.querySelectorAll('.cm-marker').length===1"),f'Installed fallback preserves marker and city mode at zoom {zoom}')
evaluate("document.querySelector('#cityNearButton').click();true")
check(evaluate("CityMapV07.inspect().mode==='near'"),'Nearby mode works on installed fallback map')
evaluate("document.querySelector('#cityAllButton').click();true")
check(evaluate("document.querySelectorAll('.cm-marker').length===1"),'City return restores installed fallback marker')
check(evaluate("window.__fallbackErrors.length===0"),'No uncaught JavaScript errors during installed fallback lifecycle')
cdp('Page.removeScriptToEvaluateOnNewDocument',{'identifier':script['identifier']})
