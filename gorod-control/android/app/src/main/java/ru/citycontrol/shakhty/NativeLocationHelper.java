package ru.citycontrol.shakhty;

import android.Manifest;
import android.app.Activity;
import android.content.Context;
import android.content.pm.PackageManager;
import android.location.Location;
import android.location.LocationListener;
import android.location.LocationManager;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;

/**
 * GPS fix from the phone, independent of the Android WebView geolocation API.
 * Only triggered by the user's tap; no background location collection.
 */
public final class NativeLocationHelper {
  public interface Callback {
    void onLocation(double latitude, double longitude, float accuracyMetres);
    void onError(String code);
  }
  private static final long TIMEOUT_MILLIS = 28000L;
  private static final long MAX_CACHE_AGE_MILLIS = 180000L;
  private final Activity activity;
  private final Handler handler = new Handler(Looper.getMainLooper());
  private final LocationManager manager;
  private LocationListener listener;
  private Runnable timeout;
  private Location best;
  private Callback callback;

  public NativeLocationHelper(Activity activity) {
    this.activity = activity;
    this.manager = (LocationManager) activity.getSystemService(Context.LOCATION_SERVICE);
  }
  private boolean hasPermission() {
    return activity.checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION)==PackageManager.PERMISSION_GRANTED
      || activity.checkSelfPermission(Manifest.permission.ACCESS_COARSE_LOCATION)==PackageManager.PERMISSION_GRANTED;
  }
  private static long ageMillis(Location location) {
    if (location==null) return Long.MAX_VALUE;
    return Math.abs(System.currentTimeMillis()-location.getTime());
  }
  private static float accuracy(Location location) {
    return location.hasAccuracy()?location.getAccuracy():5000f;
  }
  private void consider(Location location) {
    if (location==null || ageMillis(location)>MAX_CACHE_AGE_MILLIS) return;
    if (!Double.isFinite(location.getLatitude()) || !Double.isFinite(location.getLongitude())) return;
    if (best==null || accuracy(location)<accuracy(best) ||
        (accuracy(location)==accuracy(best) && ageMillis(location)<ageMillis(best))) {
      best=location;
    }
  }
  public void request(Callback cb) {
    cancel();
    callback=cb;
    if (!hasPermission()) { finishError("PERMISSION_DENIED");return; }
    if (manager==null) { finishError("UNAVAILABLE");return; }

    boolean gps,network;
    try {
      gps=manager.isProviderEnabled(LocationManager.GPS_PROVIDER);
      network=manager.isProviderEnabled(LocationManager.NETWORK_PROVIDER);
    } catch(Exception e) { finishError("UNAVAILABLE");return; }

    if(!gps && !network) {finishError("LOCATION_DISABLED");return;}
    try {
      if(network)consider(manager.getLastKnownLocation(LocationManager.NETWORK_PROVIDER));
      if(gps)consider(manager.getLastKnownLocation(LocationManager.GPS_PROVIDER));
    } catch(SecurityException e) {finishError("PERMISSION_DENIED");return;}

    // Fresh, precise phone fix: use it immediately.
    if(best!=null && ageMillis(best)<60000L && accuracy(best)<=250f) {
      finishLocation(best);
      return;
    }

    listener=new LocationListener() {
      @Override public void onLocationChanged(Location location) {
        consider(location);
        // Accept usable network fixes indoors; keep waiting for a better GPS fix if imprecise.
        if(best!=null && accuracy(best)<=650f) finishLocation(best);
      }
      @Override public void onProviderEnabled(String provider) {}
      @Override public void onProviderDisabled(String provider) {}
      @Override public void onStatusChanged(String provider,int status,Bundle extras) {}
    };

    try {
      if(network)manager.requestLocationUpdates(LocationManager.NETWORK_PROVIDER,0L,0f,listener,Looper.getMainLooper());
      if(gps)manager.requestLocationUpdates(LocationManager.GPS_PROVIDER,0L,0f,listener,Looper.getMainLooper());
    } catch(SecurityException e) {finishError("PERMISSION_DENIED");return;}
      catch(Exception e) {finishError("UNAVAILABLE");return;}

    timeout=()-> {
      if(best!=null && accuracy(best)<=2500f)finishLocation(best);
      else finishError("TIMEOUT");
    };
    handler.postDelayed(timeout,TIMEOUT_MILLIS);
  }
  private void cleanup() {
    if(timeout!=null){handler.removeCallbacks(timeout);timeout=null;}
    if(listener!=null){
      try {manager.removeUpdates(listener);} catch(Exception ignored){}
      listener=null;
    }
  }
  private void finishLocation(Location location) {
    Callback cb=callback;
    cleanup();
    callback=null;
    if(cb!=null)cb.onLocation(location.getLatitude(),location.getLongitude(),accuracy(location));
  }
  private void finishError(String error) {
    Callback cb=callback;
    cleanup();
    callback=null;
    if(cb!=null)cb.onError(error);
  }
  public void cancel() {
    cleanup();
    callback=null;
    best=null;
  }
}
