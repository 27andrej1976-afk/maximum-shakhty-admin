package ru.citycontrol.don;

import android.graphics.Bitmap;
import android.os.SystemClock;
import android.view.View;
import android.view.ViewGroup;
import android.webkit.WebView;
import androidx.test.core.app.ActivityScenario;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import java.io.File;
import java.io.FileOutputStream;
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
  @Test public void offlineShellLoadsAndDoesNotClaimRegionalCoverage() throws Exception {
    try (ActivityScenario<MainActivity> scenario = ActivityScenario.launch(MainActivity.class)) {
      loaded(scenario);
      waitFor(scenario, "document.getElementById('connection').textContent.includes('сборщик ещё не подключён')");
      assertEquals("true", js(scenario, "document.querySelector('h1').textContent==='Дон под контролем' && document.getElementById('region').textContent==='Вся область' && document.querySelectorAll('#filters button').length===5"));
      assertEquals("true", js(scenario, "document.getElementById('adSlot').hidden && document.querySelector('footer').textContent.includes('не означает отсутствие аварий')"));
      Bitmap image = InstrumentationRegistry.getInstrumentation().getUiAutomation().takeScreenshot();
      scenario.onActivity(activity -> {
        try (FileOutputStream out = new FileOutputStream(new File(activity.getExternalFilesDir(null), "don-preview.png"))) {
          if (image != null) image.compress(Bitmap.CompressFormat.PNG, 100, out);
        } catch (Exception error) { throw new AssertionError(error); }
      });
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
}
