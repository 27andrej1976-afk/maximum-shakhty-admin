package ru.citycontrol.don;

import android.content.Context;
import android.content.SharedPreferences;
import org.json.JSONObject;

final class PushSettings {
  static SharedPreferences prefs(Context c){return c.getSharedPreferences("don-push",Context.MODE_PRIVATE);}
  static boolean enabled(Context c){return prefs(c).getBoolean("enabled",false);}
  static boolean hasPoint(Context c){return prefs(c).contains("lat")&&prefs(c).contains("lon");}
  static synchronized void sync(Context c,JSONObject input) throws Exception {
    int radius=input.getInt("radius");if(radius!=1&&radius!=3&&radius!=5)throw new IllegalArgumentException();
    if(input.isNull("home")){prefs(c).edit().remove("lat").remove("lon").putInt("radius",radius).apply();PushController.disable(c);return;}
    JSONObject home=input.getJSONObject("home");double lat=home.getDouble("lat"),lon=home.getDouble("lon");
    if(!Double.isFinite(lat)||!Double.isFinite(lon)||Math.abs(lat)>90||Math.abs(lon)>180)throw new IllegalArgumentException();
    prefs(c).edit().putLong("lat",Double.doubleToLongBits(lat)).putLong("lon",Double.doubleToLongBits(lon)).putInt("radius",radius).apply();
  }
  static double lat(Context c){return Double.longBitsToDouble(prefs(c).getLong("lat",0));}
  static double lon(Context c){return Double.longBitsToDouble(prefs(c).getLong("lon",0));}
}
