package ru.citycontrol.don;

import android.graphics.Bitmap;
import android.app.Instrumentation;
import android.app.Activity;
import android.content.Intent;
import android.content.IntentFilter;
import android.os.SystemClock;
import android.os.ParcelFileDescriptor;
import android.view.View;
import android.view.ViewGroup;
import android.webkit.WebView;
import androidx.test.core.app.ActivityScenario;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import java.io.InputStream;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;
import org.junit.Test;
import org.junit.runner.RunWith;
import static org.junit.Assert.*;

@RunWith(AndroidJUnit4.class)
public class RegionalClientTest {
  private WebView findWeb(View view) {
    if (view instanceof WebView) return (WebView)view;
    if (view instanceof ViewGroup) {
      ViewGroup group = (ViewGroup)view;
      for (int n=0; n<group.getChildCount(); n++) {
        WebView found = findWeb(group.getChildAt(n));
        if (found != null) return found;
      }
    }
    return null;
  }
  private String js(ActivityScenario<MainActivity> scenario, String script) throws Exception {
    AtomicReference<String> value = new AtomicReference<>();
    CountDownLatch done = new CountDownLatch(1);
    scenario.onActivity(activity -> findWeb(activity.getWindow().getDecorView())
        .evaluateJavascript(script, result -> {value.set(result); done.countDown();}));
    assertTrue("WebView callback timed out", done.await(5, TimeUnit.SECONDS));
    return value.get();
  }
  private void waitFor(ActivityScenario<MainActivity> scenario, String condition) throws Exception {
    long deadline = SystemClock.elapsedRealtime() + 20000;
    do {
      if ("true".equals(js(scenario, condition))) return;
      SystemClock.sleep(150);
    } while (SystemClock.elapsedRealtime() < deadline);
    fail("Regional interface did not reach expected state: " + condition);
  }
  private void loaded(ActivityScenario<MainActivity> scenario) throws Exception {
    waitFor(scenario, "!!document.getElementById('map')?.classList.contains('leaflet-container') && !!document.getElementById('clearData')");
  }
  private void visibleAndFocused(ActivityScenario<MainActivity> scenario) throws Exception {
    AtomicReference<Boolean> focused = new AtomicReference<>(false);
    long deadline = SystemClock.elapsedRealtime()+10000;
    do {
      scenario.onActivity(activity -> focused.set(activity.hasWindowFocus()
          && activity.getWindow().getDecorView().isShown()));
      if (focused.get()) {
        android.view.accessibility.AccessibilityNodeInfo root =
            InstrumentationRegistry.getInstrumentation().getUiAutomation().getRootInActiveWindow();
        if (root != null && "ru.citycontrol.don".contentEquals(root.getPackageName())) return;
      }
      SystemClock.sleep(200);
    } while (SystemClock.elapsedRealtime()<deadline);
    fail("Regional app is not visibly focused; a system dialog or another app blocks the screenshot");
  }
  @Test public void offlineShellLoadsAndDoesNotClaimRegionalCoverage() throws Exception {
    try (ActivityScenario<MainActivity> scenario = ActivityScenario.launch(MainActivity.class)) {
      loaded(scenario);
      waitFor(scenario, "Array.from(document.querySelectorAll('.brands img')).every(image=>image.complete && image.naturalWidth>0)");
      waitFor(scenario,"!document.getElementById('refresh').disabled");
      js(scenario,"document.getElementById('clearData').click();window.DonConfig={feedConfigured:false};document.getElementById('refresh').click();");
      waitFor(scenario, "document.getElementById('connection').textContent.includes('сборщик ещё не подключён')");
      assertEquals("true", js(scenario, "document.querySelector('h1').textContent==='Дон под контролем' && document.getElementById('region').textContent==='Вся область' && document.querySelectorAll('#filters button').length===4 && !document.querySelector('[data-category=gas]')"));
      assertEquals("true", js(scenario, "document.getElementById('report').getAttribute('href')==='https://www.gosuslugi.ru/10091/1'"));
      assertEquals("true", js(scenario, "document.getElementById('adSlot').hidden && document.querySelector('footer').textContent.includes('не означает отсутствие аварий')"));
      visibleAndFocused(scenario);
      Bitmap image = InstrumentationRegistry.getInstrumentation().getUiAutomation().takeScreenshot();
      assertNotNull("Android screenshot must be captured", image);
      // Gradle uninstalls the tested app and removes its external-files folder.
      // The emulator shell owns this QA image outside the app sandbox, so it
      // survives test cleanup without requesting user storage permissions.
      try (InputStream proof = new ParcelFileDescriptor.AutoCloseInputStream(
          InstrumentationRegistry.getInstrumentation().getUiAutomation()
              .executeShellCommand("screencap -p /sdcard/Download/don-preview.png"))) {
        byte[] buffer = new byte[256];
        while (proof.read(buffer) != -1) { /* Wait for the shell capture to finish. */ }
      }
    }
  }
  @Test public void deletedPointCannotBeRestoredByLateLocationCallback() throws Exception {
    try (ActivityScenario<MainActivity> scenario = ActivityScenario.launch(MainActivity.class)) {
      loaded(scenario);
      js(scenario, "Object.defineProperty(navigator,'geolocation',{configurable:true,value:{getCurrentPosition:(ok)=>{window.__pendingGPS=ok}}}); document.getElementById('locate').click(); document.getElementById('forgetPoint').click(); window.__pendingGPS({coords:{latitude:47,longitude:40}});");
      assertEquals("true", js(scenario, "localStorage.getItem('don-point')===null && !document.getElementById('locate').disabled && document.getElementById('clearStatus').textContent.includes('удалена')"));
    }
  }
  @Test public void clearDataRemovesPointPreferencesAndFeed() throws Exception {
    try (ActivityScenario<MainActivity> scenario = ActivityScenario.launch(MainActivity.class)) {
      loaded(scenario);
      js(scenario, "for(const k of ['don-point','don-radius','don-preferences','don-feed'])localStorage.setItem(k,'synthetic-fixture'); document.getElementById('clearData').click();");
      assertEquals("true", js(scenario, "['don-point','don-radius','don-preferences','don-feed'].every(k=>localStorage.getItem(k)===null) && document.getElementById('eventCount').textContent==='0' && document.getElementById('radius').value==='1'"));
    }
  }
  @Test public void reportOpensExternalOfficialServiceWithoutSubmittingAnything() throws Exception {
    try (ActivityScenario<MainActivity> scenario = ActivityScenario.launch(MainActivity.class)) {
      loaded(scenario);
      Instrumentation instrumentation = InstrumentationRegistry.getInstrumentation();
      IntentFilter filter = new IntentFilter(Intent.ACTION_VIEW);
      filter.addDataScheme("https");
      Instrumentation.ActivityMonitor monitor = instrumentation.addMonitor(filter,
          new Instrumentation.ActivityResult(Activity.RESULT_CANCELED, null), true);
      try {
        assertEquals("true", js(scenario, "document.getElementById('report').href==='https://www.gosuslugi.ru/10091/1'"));
        js(scenario, "document.getElementById('report').click(); true");
        long deadline = SystemClock.elapsedRealtime()+5000;
        while (monitor.getHits()==0 && SystemClock.elapsedRealtime()<deadline) SystemClock.sleep(100);
        assertEquals("Must delegate exactly one external navigation", 1, monitor.getHits());
        assertEquals("true", js(scenario, "location.hostname==='appassets.androidplatform.net'"));
      } finally {
        instrumentation.removeMonitor(monitor);
      }
    }
  }
  private void showElement(ActivityScenario<MainActivity> scenario, String id) throws Exception {
    // Correct from the current native scroll offset: opening details and Leaflet
    // updates can move the target after the initial DOM offset was measured.
    for (int attempt=0; attempt<4; attempt++) {
      double delta=Double.parseDouble(js(scenario,"document.getElementById('"+id+"').getBoundingClientRect().top"));
      scenario.onActivity(activity -> {
        WebView view=findWeb(activity.getWindow().getDecorView());
        view.scrollBy(0,(int)Math.round(delta*view.getScale()));
        view.invalidate();
      });
      InstrumentationRegistry.getInstrumentation().waitForIdleSync();
      SystemClock.sleep(350);
      if ("true".equals(js(scenario,"(()=>{const r=document.getElementById('"+id+"').getBoundingClientRect();return r.top<innerHeight/2 && Math.min(r.bottom,innerHeight)-Math.max(r.top,0)>Math.min(r.height,innerHeight)*0.7})()"))) return;
    }
    captureProof(scenario,"don-scroll-failure-"+id);
    fail("Target is not sufficiently visible: "+js(scenario,"(()=>{const r=document.getElementById('"+id+"').getBoundingClientRect();return JSON.stringify({top:r.top,bottom:r.bottom,height:r.height,viewport:innerHeight,scroll:scrollY})})()"));
  }
  private void captureProof(ActivityScenario<MainActivity> scenario, String name) throws Exception {
    visibleAndFocused(scenario);
    try (InputStream proof = new ParcelFileDescriptor.AutoCloseInputStream(
        InstrumentationRegistry.getInstrumentation().getUiAutomation()
          .executeShellCommand("screencap -p /sdcard/Download/"+name+".png"))) {
      byte[] buffer = new byte[256];
      while (proof.read(buffer) != -1) { }
    }
  }
  private void realFeed(ActivityScenario<MainActivity> scenario) throws Exception {
    loaded(scenario);
    waitFor(scenario,"!document.getElementById('refresh').disabled");
    js(scenario, "window.DonConfig={feedConfigured:true,feedURL:'https://appassets.androidplatform.net/assets/web/qa/real-feed.json'}; document.getElementById('refresh').click();");
    waitFor(scenario,"JSON.parse(localStorage.getItem('don-feed')||'{}').verificationMode==='real-MAX-to-Android-QA-export-not-a-deployment' && !document.getElementById('refresh').disabled");
    js(scenario,"document.getElementById('city').value=''; document.getElementById('city').dispatchEvent(new Event('change')); document.getElementById('region').click(); document.querySelector('[data-category=all]').click();");
  }
  @Test public void realMAXExportRendersAllCategoriesAndPreservesMarkersOffline() throws Exception {
    try (ActivityScenario<MainActivity> scenario = ActivityScenario.launch(MainActivity.class)) {
      realFeed(scenario);
      assertEquals("true", js(scenario,"document.querySelectorAll('#map .leaflet-marker-icon').length>=6"));
      for (String category : new String[]{"water","power","mchs"}) {
        js(scenario,"document.querySelector('[data-category="+category+"]').click();");
        assertEquals("true", js(scenario,"Number(document.getElementById('eventCount').textContent)>0"));
      }
      js(scenario,"document.querySelector('[data-category=water]').click(); document.querySelector('#events details').open=true; document.getElementById('map').scrollIntoView({block:'start'});");
      assertEquals("true",js(scenario,"document.querySelectorAll('#map .leaflet-marker-icon').length>=3 && document.getElementById('events').textContent.includes('Белая Калитва')"));
      js(scenario,"(()=>{const f=JSON.parse(localStorage.getItem('don-feed'));document.getElementById('city').value=f.events.find(e=>e.category==='water').municipalityId;document.getElementById('city').dispatchEvent(new Event('change'))})()");
      showElement(scenario,"map");
      captureProof(scenario,"don-real-water-map");
      js(scenario,"document.getElementById('events').scrollIntoView({block:'start'});");
      js(scenario,"document.querySelector('#events details').open=true;");
      showElement(scenario,"events");
      captureProof(scenario,"don-real-water-card");
      js(scenario,"window.__countBeforeOffline=document.getElementById('eventCount').textContent; window.__savedFetch=window.fetch; window.fetch=()=>Promise.reject(new Error('QA_OFFLINE')); document.getElementById('refresh').click();");
      waitFor(scenario,"document.getElementById('connection').textContent.includes('Сервер недоступен')");
      assertEquals("true",js(scenario,"document.getElementById('eventCount').textContent===window.__countBeforeOffline && document.querySelectorAll('#map .leaflet-marker-icon').length>=3 && document.querySelectorAll('#healthCards .unavailable').length===3"));
      js(scenario,"window.fetch=window.__savedFetch; document.getElementById('refresh').click();");
      waitFor(scenario,"document.getElementById('connection').textContent.includes('Контрольная проверка')");
    }
  }
  @Test public void deployedHttpsFeedReachesAndroidOverNetwork() throws Exception {
    try (ActivityScenario<MainActivity> scenario=ActivityScenario.launch(MainActivity.class)) {
      loaded(scenario);
      waitFor(scenario,"!document.getElementById('refresh').disabled");
      js(scenario,"document.getElementById('clearData').click();window.DonConfig={feedConfigured:true,feedURL:'https://chat.sportoskop.ru/don-control/feed.json'};document.getElementById('refresh').click();");
      waitFor(scenario,"!document.getElementById('refresh').disabled && document.getElementById('connection').textContent.includes('Сводка получена')");
      assertEquals("true",js(scenario,"(()=>{const f=JSON.parse(localStorage.getItem('don-feed'));return f.dataMode==='production' && f.mode==='max-only' && !f.verificationMode && Date.now()-Date.parse(f.generatedAt)<600000})()"));
      js(scenario,"document.getElementById('city').value='';document.getElementById('city').dispatchEvent(new Event('change'));document.querySelector('[data-category=all]').click();");
      assertEquals("true",js(scenario,"document.querySelectorAll('#map .leaflet-marker-icon').length>=3 && Number(document.getElementById('eventCount').textContent)>0"));
      for (String category:new String[]{"water","power","mchs"}) {
        js(scenario,"document.querySelector('[data-category="+category+"]').click();");
        assertEquals("true",js(scenario,"Number(document.getElementById('eventCount').textContent)>0"));
      }
    }
  }
  @Test public void systemGeolocationFiltersRealPublicationMarkersNearEmulatorPoint() throws Exception {
    InstrumentationRegistry.getInstrumentation().getUiAutomation().grantRuntimePermission("ru.citycontrol.don", "android.permission.ACCESS_FINE_LOCATION");
    InstrumentationRegistry.getInstrumentation().getUiAutomation().grantRuntimePermission("ru.citycontrol.don", "android.permission.ACCESS_COARSE_LOCATION");
    try (ActivityScenario<MainActivity> scenario = ActivityScenario.launch(MainActivity.class)) {
      realFeed(scenario);
      js(scenario,"document.getElementById('forgetPoint').click(); document.querySelector('[data-category=water]').click(); document.getElementById('locate').click();");
      waitFor(scenario,"!!JSON.parse(localStorage.getItem('don-point')||'null') && !document.getElementById('locate').disabled");
      assertEquals("true",js(scenario,"Number(document.getElementById('eventCount').textContent)>0 && document.getElementById('near').getAttribute('aria-pressed')==='true'"));
      assertEquals("true",js(scenario,"(()=>{const p=JSON.parse(localStorage.getItem('don-point')); const f=JSON.parse(localStorage.getItem('don-feed'));return f.events.filter(e=>e.category==='water').some(e=>e.addresses.some(a=>a.geometryVerified&&DonClient.distance(p,a)<0.2))})()"));
      js(scenario,"document.getElementById('map').scrollIntoView({block:'start'});");
      showElement(scenario,"map");
      captureProof(scenario,"don-real-near-system-gps");
      js(scenario,"document.getElementById('forgetPoint').click();");
    }
  }

}
