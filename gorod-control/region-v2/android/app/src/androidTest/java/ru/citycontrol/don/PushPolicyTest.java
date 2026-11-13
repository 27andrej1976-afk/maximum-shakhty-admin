package ru.citycontrol.don;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.json.JSONObject;
import org.json.JSONArray;
import java.time.Instant;
import static org.junit.Assert.*;

@RunWith(AndroidJUnit4.class)
public class PushPolicyTest {
  final long now=Instant.parse("2026-11-13T10:00:00Z").toEpochMilli();
  JSONObject fixture() throws Exception {
    JSONObject address=new JSONObject().put("id","street").put("geometryVerified",true).put("lat",47.2).put("lon",39.7);
    JSONObject event=new JSONObject().put("id","water-1").put("sourceHash","a".repeat(64)).put("category","water").put("status","active").put("scope","municipality").put("publishedAt","2026-11-13T09:50:00Z").put("expiresAt","2026-11-14T10:00:00Z").put("addresses",new JSONArray().put(address));
    return new JSONObject().put("schemaVersion",1).put("regionId","RU-ROS").put("mode","max-only").put("dataMode","production").put("generatedAt","2026-11-13T10:00:00Z").put("events",new JSONArray().put(event));
  }
  JSONObject event(JSONObject f) throws Exception {return f.getJSONArray("events").getJSONObject(0);}
  JSONObject find(JSONObject f,double lat,double lon) throws Exception {return PushPolicy.find(f,"water-1","a".repeat(64),lat,lon,1,now);}
  @Test public void only_verified_in_radius_event_can_notify() throws Exception {
    JSONObject f=fixture();assertNotNull(find(f,47.2,39.7));assertNull(find(f,48,40));
    event(f).getJSONArray("addresses").getJSONObject(0).put("geometryVerified",false);assertNull(find(f,47.2,39.7));
  }
  @Test public void restored_changed_expired_and_wrong_hash_are_suppressed() throws Exception {
    JSONObject f=fixture();event(f).put("status","resolved");assertNull(find(f,47.2,39.7));
    f=fixture();event(f).put("sourceChanged",true);assertNull(find(f,47.2,39.7));
    f=fixture();event(f).put("expiresAt","2026-11-13T10:00:00Z");assertNull(find(f,47.2,39.7));
    f=fixture();assertNull(PushPolicy.find(f,"water-1","b".repeat(64),47.2,39.7,1,now));
  }
  @Test public void stale_historical_and_test_data_do_not_notify() throws Exception {
    JSONObject f=fixture();f.put("generatedAt","2026-11-13T09:00:00Z");assertNull(find(f,47.2,39.7));
    f=fixture();f.put("verificationMode",true);assertNull(find(f,47.2,39.7));
    f=fixture();f.put("dataMode","test");assertNull(find(f,47.2,39.7));
  }
  @Test public void only_verified_region_mchs_is_independent_of_radius() throws Exception {
    JSONObject f=fixture();event(f).put("scope","region");assertNotNull(find(f,47.2,39.7));assertNull(find(f,48,40));
    event(f).put("category","mchs");assertNotNull(find(f,48,40));
  }
  @Test public void clearing_point_disables_native_push_and_no_project_never_claims_active() throws Exception {
    android.content.Context c=InstrumentationRegistry.getInstrumentation().getTargetContext();
    PushSettings.sync(c,new JSONObject().put("home",new JSONObject().put("lat",47.2).put("lon",39.7)).put("radius",1));assertTrue(PushSettings.hasPoint(c));
    PushSettings.prefs(c).edit().putBoolean("enabled",true).apply();
    PushSettings.sync(c,new JSONObject().put("home",JSONObject.NULL).put("radius",1));assertFalse(PushSettings.hasPoint(c));assertFalse(PushSettings.enabled(c));
    assertFalse(PushController.status(c).getBoolean("enabled"));assertTrue(PushController.status(c).getString("message").contains("не подключён"));
  }
}
