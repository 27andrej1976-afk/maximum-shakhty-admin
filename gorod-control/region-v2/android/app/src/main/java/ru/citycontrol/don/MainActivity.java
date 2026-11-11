package ru.citycontrol.don;

import android.Manifest;
import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.webkit.CookieManager;
import android.webkit.GeolocationPermissions;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.FrameLayout;
import android.widget.Toast;
import androidx.webkit.WebViewAssetLoader;
import java.io.ByteArrayInputStream;

/** Regional client. No MAX session, credentials, accounts or background GPS. */
public final class MainActivity extends Activity {
  private static final String HOST = "appassets.androidplatform.net";
  private static final String HOME = "https://" + HOST + "/assets/web/index.html";
  private static final int GEO_REQUEST = 701;
  private WebView web;
  private GeolocationPermissions.Callback pendingGeo;
  private String pendingOrigin;

  private boolean trusted(Uri uri) {
    return uri != null && "https".equals(uri.getScheme()) && HOST.equals(uri.getHost())
        && (uri.getPort() == -1 || uri.getPort() == 443)
        && uri.getUserInfo() == null && "/assets/web/index.html".equals(uri.getPath());
  }

  private void cancelPendingLocation() {
    if (pendingGeo != null) pendingGeo.invoke(pendingOrigin, false, false);
    pendingGeo = null;
    pendingOrigin = null;
  }

  @Override public void onCreate(Bundle savedState) {
    super.onCreate(savedState);
    getWindow().setStatusBarColor(Color.rgb(16, 46, 70));
    getWindow().setNavigationBarColor(Color.rgb(16, 46, 70));
    FrameLayout container = new FrameLayout(this);
    container.setOnApplyWindowInsetsListener((view, insets) -> {
      view.setPadding(insets.getSystemWindowInsetLeft(), insets.getSystemWindowInsetTop(),
          insets.getSystemWindowInsetRight(), insets.getSystemWindowInsetBottom());
      return insets.consumeSystemWindowInsets();
    });
    web = new WebView(this);
    container.addView(web, new FrameLayout.LayoutParams(-1, -1));
    setContentView(container);
    container.requestApplyInsets();
    WebView.setWebContentsDebuggingEnabled(BuildConfig.DEBUG);
    WebSettings settings = web.getSettings();
    settings.setJavaScriptEnabled(true);
    settings.setDomStorageEnabled(true);
    settings.setGeolocationEnabled(true);
    settings.setAllowFileAccess(false);
    settings.setAllowContentAccess(false);
    settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
    settings.setJavaScriptCanOpenWindowsAutomatically(false);
    settings.setSafeBrowsingEnabled(true);
    settings.setUserAgentString(settings.getUserAgentString() + " DonControl/0.1-preview");
    CookieManager.getInstance().setAcceptThirdPartyCookies(web, false);
    WebViewAssetLoader loader = new WebViewAssetLoader.Builder()
        .addPathHandler("/assets/", new WebViewAssetLoader.AssetsPathHandler(this)).build();
    web.setWebViewClient(new WebViewClient() {
      @Override public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request) {
        Uri uri = request.getUrl();
        WebResourceResponse response = loader.shouldInterceptRequest(uri);
        // Never fall through from missing app assets to a real network host.
        if (response == null && HOST.equals(uri.getHost()))
          return new WebResourceResponse("text/plain", "UTF-8", 404, "Not found",
              java.util.Collections.emptyMap(), new ByteArrayInputStream(new byte[0]));
        return response;
      }
      @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
        Uri uri = request.getUrl();
        if (!request.isForMainFrame()) return true;
        if (trusted(uri)) return false;
        if (HOST.equals(uri.getHost()) && "https".equals(uri.getScheme())
            && "/assets/web/about.html".equals(uri.getPath())) return false;
        if ("https".equals(uri.getScheme()) && uri.getUserInfo() == null) {
          cancelPendingLocation();
          try { startActivity(new Intent(Intent.ACTION_VIEW, uri)); }
          catch (ActivityNotFoundException error) {
            Toast.makeText(MainActivity.this, "Не найден браузер для открытия ссылки", Toast.LENGTH_LONG).show();
          }
        }
        return true;
      }
      @Override public void onPageStarted(WebView view, String url, android.graphics.Bitmap icon) {
        cancelPendingLocation();
      }
    });
    web.setWebChromeClient(new WebChromeClient() {
      @Override public void onGeolocationPermissionsShowPrompt(String origin, GeolocationPermissions.Callback callback) {
        Uri uri = Uri.parse(origin);
        if (!"https".equals(uri.getScheme()) || !HOST.equals(uri.getHost())
            || (uri.getPort() != -1 && uri.getPort() != 443) || uri.getUserInfo() != null
            || web == null || !trusted(Uri.parse(web.getUrl() == null ? "" : web.getUrl()))) {
          callback.invoke(origin, false, false);
          return;
        }
        cancelPendingLocation();
        if (hasLocationPermission()) { callback.invoke(origin, true, false); return; }
        pendingGeo = callback;
        pendingOrigin = origin;
        requestPermissions(new String[]{Manifest.permission.ACCESS_FINE_LOCATION,
            Manifest.permission.ACCESS_COARSE_LOCATION}, GEO_REQUEST);
      }
    });
    web.loadUrl(HOME);
  }

  private boolean hasLocationPermission() {
    return checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED
        || checkSelfPermission(Manifest.permission.ACCESS_COARSE_LOCATION) == PackageManager.PERMISSION_GRANTED;
  }

  @Override public void onRequestPermissionsResult(int code, String[] permissions, int[] grants) {
    super.onRequestPermissionsResult(code, permissions, grants);
    if (code == GEO_REQUEST && pendingGeo != null) {
      boolean allowed = hasLocationPermission() && web != null
          && trusted(Uri.parse(web.getUrl() == null ? "" : web.getUrl()));
      pendingGeo.invoke(pendingOrigin, allowed, false);
      pendingGeo = null;
      pendingOrigin = null;
    }
  }

  @Override public void onBackPressed() {
    if (web != null && web.canGoBack()) web.goBack(); else super.onBackPressed();
  }

  @Override protected void onDestroy() {
    cancelPendingLocation();
    if (web != null) { web.stopLoading(); web.destroy(); web = null; }
    super.onDestroy();
  }
}
