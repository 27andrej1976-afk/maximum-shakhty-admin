package ru.citycontrol.shakhty;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Bundle;
import android.webkit.GeolocationPermissions;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.webkit.WebResourceRequest;
import android.widget.FrameLayout;
import android.graphics.Color;

public final class MainActivity extends Activity {
  private static final String URL =
      "https://27andrej1976-afk.github.io/maximum-shakhty-admin/gorod-control/";
  private static final String TRUSTED_HOST = "27andrej1976-afk.github.io";
  private static final String TRUSTED_PATH = "/maximum-shakhty-admin/gorod-control/";
  private static final int GEO_REQUEST = 615;
  private WebView web;
  private GeolocationPermissions.Callback pendingGeo;
  private String pendingGeoOrigin;

  @Override public void onCreate(Bundle saved) {
    super.onCreate(saved);
    getWindow().setStatusBarColor(Color.rgb(16,26,44));
    getWindow().setNavigationBarColor(Color.rgb(16,26,44));
    FrameLayout container = new FrameLayout(this);
    web = new WebView(this);
    web.setBackgroundColor(Color.rgb(243,246,248));
    container.addView(web,new FrameLayout.LayoutParams(-1,-1));
    setContentView(container);
    WebSettings settings = web.getSettings();
    settings.setJavaScriptEnabled(true);
    settings.setDomStorageEnabled(true);
    settings.setGeolocationEnabled(true);
    settings.setAllowFileAccess(false);
    settings.setAllowContentAccess(false);
    settings.setJavaScriptCanOpenWindowsAutomatically(false);
    settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
    web.setWebViewClient(new WebViewClient(){
      @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
        Uri target = request.getUrl();
        if ("https".equals(target.getScheme()) && TRUSTED_HOST.equals(target.getHost())
          && target.getPath()!=null && target.getPath().startsWith(TRUSTED_PATH)) return false;
        try {
          if ("https".equals(target.getScheme()))
            startActivity(new Intent(Intent.ACTION_VIEW,target));
        } catch(Exception ignored) {}
        return true;
      }
    });
    web.setWebChromeClient(new WebChromeClient(){
      @Override public void onGeolocationPermissionsShowPrompt(String origin,
          GeolocationPermissions.Callback callback) {
        if (!origin.equals("https://"+TRUSTED_HOST)) {
          callback.invoke(origin,false,false);return;
        }
        if (checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION)==PackageManager.PERMISSION_GRANTED ||
            checkSelfPermission(Manifest.permission.ACCESS_COARSE_LOCATION)==PackageManager.PERMISSION_GRANTED) {
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
  @Override public void onRequestPermissionsResult(int code,String[] permissions,int[] grants) {
    super.onRequestPermissionsResult(code,permissions,grants);
    if (code==GEO_REQUEST && pendingGeo!=null) {
      boolean granted=false;
      for(int permission:grants) if(permission==PackageManager.PERMISSION_GRANTED) granted=true;
      pendingGeo.invoke(pendingGeoOrigin,granted,false);
      pendingGeo=null;
      pendingGeoOrigin=null;
    }
  }
  @Override public void onBackPressed() {
    if (web!=null && web.canGoBack()) web.goBack();
    else super.onBackPressed();
  }
  @Override protected void onDestroy() {
    if (web!=null){web.destroy();web=null;}
    super.onDestroy();
  }
}
