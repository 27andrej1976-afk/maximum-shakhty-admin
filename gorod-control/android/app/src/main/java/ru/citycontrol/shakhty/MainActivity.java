package ru.citycontrol.shakhty;

import android.Manifest;
import android.app.Activity;
import android.app.AlertDialog;
import android.app.job.JobInfo;
import android.app.job.JobScheduler;
import android.content.ComponentName;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import java.util.Locale;
import android.webkit.GeolocationPermissions;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.FrameLayout;

import org.json.JSONObject;
import org.json.JSONTokener;

public final class MainActivity extends Activity {
  private static final String URL =
      "https://27andrej1976-afk.github.io/maximum-shakhty-admin/gorod-control/";
  private static final String TRUSTED_HOST = "27andrej1976-afk.github.io";
  private static final String TRUSTED_PATH = "/maximum-shakhty-admin/gorod-control/";
  private static final int GEO_REQUEST = 615;
  private static final int NOTIFY_REQUEST = 616;
  private static final int PHONE_GPS_REQUEST = 617;
  private final Handler handler=new Handler(Looper.getMainLooper());
  private WebView web;
  private NativeLocationHelper nativeLocation;
  private GeolocationPermissions.Callback pendingGeo;
  private String pendingGeoOrigin;
  private final Runnable homeSync=new Runnable(){
    @Override public void run(){
      syncHome();
      if(web!=null)handler.postDelayed(this,8000);
    }
  };

  @Override public void onCreate(Bundle saved) {
    super.onCreate(saved);
    getWindow().setStatusBarColor(Color.rgb(16,26,44));
    getWindow().setNavigationBarColor(Color.rgb(16,26,44));
    scheduleWaterMonitor();
    nativeLocation=new NativeLocationHelper(this);
    FrameLayout container = new FrameLayout(this);
    web = new WebView(this);
    web.setBackgroundColor(Color.rgb(243,246,248));
    container.addView(web,new FrameLayout.LayoutParams(-1,-1));
    setContentView(container);
    WebSettings settings=web.getSettings();
    settings.setUserAgentString(settings.getUserAgentString() + " CityControlApp/0.4");
    settings.setJavaScriptEnabled(true);
    settings.setDomStorageEnabled(true);
    settings.setGeolocationEnabled(true);
    settings.setAllowFileAccess(false);
    settings.setAllowContentAccess(false);
    settings.setJavaScriptCanOpenWindowsAutomatically(false);
    settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
    if(Build.VERSION.SDK_INT>=26)settings.setSafeBrowsingEnabled(true);
    web.setWebViewClient(new WebViewClient(){
      @Override public boolean shouldOverrideUrlLoading(WebView view,WebResourceRequest request){
        Uri target=request.getUrl();
        if("citycontrol".equals(target.getScheme()) && "get-location".equals(target.getHost())){
          if(request.isForMainFrame() && isTrustedPage(view.getUrl()))startNativeGPS();
          return true;
        }
        if("citycontrol".equals(target.getScheme()) && "test-notification".equals(target.getHost())){
          if(view.getUrl()!=null && view.getUrl().startsWith(URL)){
            if(!WaterMonitorJobService.showTestNotification(MainActivity.this)){
              new AlertDialog.Builder(MainActivity.this)
                .setTitle("Разрешите уведомления")
                .setMessage("Для проверочных и настоящих уведомлений разрешите их в настройках Android.")
                .setPositiveButton("Разрешить",(dialog,which)->{
                  if(Build.VERSION.SDK_INT>=33)
                    requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS},NOTIFY_REQUEST);
                }).setNegativeButton("Позже",null).show();
            }
          }
          return true;
        }
        if("https".equals(target.getScheme()) && TRUSTED_HOST.equals(target.getHost())
           && target.getPath()!=null && target.getPath().startsWith(TRUSTED_PATH)) return false;
        try{
          if("https".equals(target.getScheme()))
            startActivity(new Intent(Intent.ACTION_VIEW,target));
        }catch(Exception ignored){}
        return true;
      }
      @Override public void onPageFinished(WebView view,String url){
        super.onPageFinished(view,url);
        syncHome();
      }
      @Override public void onReceivedError(WebView view,WebResourceRequest request,WebResourceError error){
        if(request.isForMainFrame()){
          String fallback="<html lang='ru'><meta name='viewport' content='width=device-width, initial-scale=1'>"
             +"<body style='font:16px system-ui;background:#101a2c;color:#fff;padding:28px'>"
             +"<h2>Нет соединения</h2><p>Для карты и проверки коммунальных сообщений нужен интернет.</p>"
             +"<a style='color:#6ad5bc' href='"+URL+"'>Повторить подключение</a></body></html>";
          view.loadDataWithBaseURL(URL,fallback,"text/html","UTF-8",null);
        }
      }
    });
    web.setWebChromeClient(new WebChromeClient(){
      @Override public void onGeolocationPermissionsShowPrompt(String origin,GeolocationPermissions.Callback callback){
        Uri originUri=Uri.parse(origin);
        // Chromium may supply origin with a trailing slash or a default HTTPS port.
        if(!"https".equalsIgnoreCase(originUri.getScheme())
            || !TRUSTED_HOST.equalsIgnoreCase(originUri.getHost())
            || (originUri.getPort()!=-1 && originUri.getPort()!=443)
            || !isTrustedPage(web!=null?web.getUrl():null)){
          callback.invoke(origin,false,false);return;
        }
        if(checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION)==PackageManager.PERMISSION_GRANTED ||
            checkSelfPermission(Manifest.permission.ACCESS_COARSE_LOCATION)==PackageManager.PERMISSION_GRANTED){
          callback.invoke(origin,true,false);return;
        }
        pendingGeo=callback;
        pendingGeoOrigin=origin;
        requestPermissions(new String[]{Manifest.permission.ACCESS_FINE_LOCATION,
          Manifest.permission.ACCESS_COARSE_LOCATION},GEO_REQUEST);
      }
    });
    web.loadUrl(URL);
  }

  private boolean isTrustedPage(String url) {
    return url!=null && (url.equals(URL) || url.startsWith(URL+"index.html")
        || url.startsWith(URL+"?") || url.startsWith(URL+"#"));
  }

  // Send only numeric coordinates to the trusted main frame; never expose GPS to another origin.
  private void deliverNativeCoordinates(double lat,double lon,float accuracyMetres) {
    if(!isTrustedPage(web!=null?web.getUrl():null))return;
    if(!Double.isFinite(lat)||!Double.isFinite(lon)||!Float.isFinite(accuracyMetres))return;
    final String payload=String.format(Locale.US,
      "window.CityControlNativeGPSResult && window.CityControlNativeGPSResult({lat:%.7f,lon:%.7f,accuracy:%.1f});",
      lat,lon,accuracyMetres);
    web.evaluateJavascript(payload,null);
  }

  private void deliverNativeError(String code) {
    if(!isTrustedPage(web!=null?web.getUrl():null))return;
    String safe;
    switch(code){
      case "PERMISSION_DENIED":safe="PERMISSION_DENIED";break;
      case "LOCATION_DISABLED":safe="LOCATION_DISABLED";break;
      case "TIMEOUT":safe="TIMEOUT";break;
      default:safe="UNAVAILABLE";
    }
    web.evaluateJavascript(
      "window.CityControlNativeGPSError && window.CityControlNativeGPSError('"+safe+"');",null);
  }

  private void startNativeGPS() {
    if(!isTrustedPage(web!=null?web.getUrl():null))return;
    boolean fine=checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION)==PackageManager.PERMISSION_GRANTED;
    boolean coarse=checkSelfPermission(Manifest.permission.ACCESS_COARSE_LOCATION)==PackageManager.PERMISSION_GRANTED;
    if(!fine && !coarse) {
      requestPermissions(new String[]{Manifest.permission.ACCESS_FINE_LOCATION,
        Manifest.permission.ACCESS_COARSE_LOCATION},PHONE_GPS_REQUEST);
      return;
    }
    if(nativeLocation==null)nativeLocation=new NativeLocationHelper(this);
    nativeLocation.request(new NativeLocationHelper.Callback(){
      @Override public void onLocation(double lat,double lon,float accuracyMetres){
        deliverNativeCoordinates(lat,lon,accuracyMetres);
      }
      @Override public void onError(String code){deliverNativeError(code);}
    });
  }

  private void scheduleWaterMonitor() {
    JobScheduler scheduler=(JobScheduler)getSystemService(JOB_SCHEDULER_SERVICE);
    if(scheduler==null)return;
    JobInfo job=new JobInfo.Builder(WaterMonitorJobService.JOB_ID,
        new ComponentName(this,WaterMonitorJobService.class))
        .setPeriodic(15*60*1000L)
        .setRequiredNetworkType(JobInfo.NETWORK_TYPE_ANY)
        .setPersisted(true).build();
    try{scheduler.schedule(job);}catch(Exception ignored){}
  }

  private void syncHome(){
    if(web==null)return;
    web.evaluateJavascript("window.localStorage.getItem('gorod_control_home_v1')",value->{
      try{
        Object decoded=new JSONTokener(value).nextValue();
        if(!(decoded instanceof String))return;
        JSONObject item=new JSONObject((String)decoded);
        String street=item.optString("street","").trim();
        String house=item.optString("house","").trim();
        if(street.isEmpty())return;
        SharedPreferences prefs=getSharedPreferences("city-control-home",MODE_PRIVATE);
        if(!street.equals(prefs.getString("street",""))||!house.equals(prefs.getString("house",""))){
          prefs.edit().putString("street",street).putString("house",house).apply();
        }
        if(Build.VERSION.SDK_INT>=33 &&
           checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)!=PackageManager.PERMISSION_GRANTED &&
           !prefs.getBoolean("asked-notification",false)){
          prefs.edit().putBoolean("asked-notification",true).apply();
          requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS},NOTIFY_REQUEST);
        }
      }catch(Exception ignored){}
    });
  }

  @Override public void onRequestPermissionsResult(int code,String[] permissions,int[] grants) {
    super.onRequestPermissionsResult(code,permissions,grants);
    if(code==PHONE_GPS_REQUEST){
      boolean granted=false;
      for(int permission:grants)if(permission==PackageManager.PERMISSION_GRANTED)granted=true;
      if(granted)startNativeGPS();
      else deliverNativeError("PERMISSION_DENIED");
      return;
    }
    if(code==GEO_REQUEST && pendingGeo!=null){
      boolean granted=false;
      for(int permission:grants)if(permission==PackageManager.PERMISSION_GRANTED)granted=true;
      pendingGeo.invoke(pendingGeoOrigin,granted,false);
      pendingGeo=null;pendingGeoOrigin=null;
    }
  }
  @Override protected void onResume(){
    super.onResume();
    handler.removeCallbacks(homeSync);
    handler.postDelayed(homeSync,2500);
  }
  @Override protected void onPause(){
    syncHome();
    handler.removeCallbacks(homeSync);
    super.onPause();
  }
  @Override public void onBackPressed() {
    if(web!=null&&web.canGoBack())web.goBack();
    else super.onBackPressed();
  }
  @Override protected void onDestroy() {
    if(nativeLocation!=null)nativeLocation.cancel();
    handler.removeCallbacks(homeSync);
    if(web!=null){web.destroy();web=null;}
    super.onDestroy();
  }
}
