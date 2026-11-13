package ru.citycontrol.don;

import org.json.JSONArray;
import org.json.JSONObject;
import java.time.Instant;

/** Same conservative eligibility as the map; messages never supply trusted content. */
final class PushPolicy {
  static boolean fresh(JSONObject feed,long now) throws Exception {
    long age=now-Instant.parse(feed.getString("generatedAt")).toEpochMilli();
    return feed.optInt("schemaVersion")==1&&"RU-ROS".equals(feed.optString("regionId"))&&"max-only".equals(feed.optString("mode"))&&"production".equals(feed.optString("dataMode"))&&!feed.optBoolean("verificationMode")&&age>=-300000&&age<=900000;
  }
  static JSONObject find(JSONObject feed,String id,String hash,double lat,double lon,int radius,long now) throws Exception {
    if(!fresh(feed,now)||!Double.isFinite(lat)||!Double.isFinite(lon)||Math.abs(lat)>90||Math.abs(lon)>180||(radius!=1&&radius!=3&&radius!=5))return null;
    JSONArray events=feed.getJSONArray("events");
    for(int i=0;i<events.length();i++){
      JSONObject e=events.getJSONObject(i);
      if(!id.equals(e.optString("id"))||!hash.equals(e.optString("sourceHash"))||e.optBoolean("sourceChanged")||e.optBoolean("requiresReview")||!"active".equals(e.optString("status")))continue;
      String cat=e.optString("category");if(!java.util.Arrays.asList("water","power","mchs").contains(cat))continue;
      if(Instant.parse(e.getString("publishedAt")).toEpochMilli()>now||Instant.parse(e.getString("expiresAt")).toEpochMilli()<=now)continue;
      if("region".equals(e.optString("scope"))&&"mchs".equals(cat))return e;
      JSONArray addresses=e.getJSONArray("addresses");
      for(int j=0;j<addresses.length();j++){
        JSONObject a=addresses.getJSONObject(j);double la=a.optDouble("lat"),lo=a.optDouble("lon");
        if(!a.optBoolean("geometryVerified")||!Double.isFinite(la)||!Double.isFinite(lo)||Math.abs(la)>90||Math.abs(lo)>180)continue;
        double dlat=Math.toRadians(la-lat),dlon=Math.toRadians(lo-lon);
        double h=Math.sin(dlat/2)*Math.sin(dlat/2)+Math.cos(Math.toRadians(lat))*Math.cos(Math.toRadians(la))*Math.sin(dlon/2)*Math.sin(dlon/2);
        double distance=6371*2*Math.asin(Math.min(1,Math.sqrt(h)));
        if(distance<=radius)return e;
      }
    }return null;
  }
}
