import ru.citycontrol.shakhty.NativeFeedMerge;
import java.time.*;
import java.util.*;

/** No Android, JSON library, network or wall-clock dependency. Run with the shipped merge policy. */
public final class NativeFeedMergeCheck {
  static int checks=0;
  static final Instant NOW=Instant.parse("2026-10-29T10:00:00Z");
  static Map<String,Object> map(Object... args){Map<String,Object> m=new LinkedHashMap<>();for(int i=0;i<args.length;i+=2)m.put((String)args[i],args[i+1]);return m;}
  static Map<String,Object> source(String id,String stamp){return map("id",id,"status","ok","checkedAt",stamp);}
  static Map<String,Object> event(String id,String sid,String origin,String url){return map("id",id,"sourceId",sid,"origin",origin,"url",url,"category","water","status","active","start","2026-10-29T07:00:00Z","end","2026-10-29T15:00:00Z","publishedAt","2026-10-29T07:30:00Z","affected",List.of(map("street","ул Тестовая","houses",List.of("1"))));}
  static Map<String,Object> kvu(String id){return event(id,"water_kvu","media_report","https://kvu.su/utilities/19357-test.html");}
  static Map<String,Object> feed(String stamp,List<?> sources,List<?> events){return map("schema",2,"checkedAt",stamp,"sources",sources,"events",events);}
  @SuppressWarnings("unchecked") static List<Map<String,Object>> rows(Map<String,Object> f,String k){return (List<Map<String,Object>>)f.get(k);}
  static Map<String,Object> row(Map<String,Object> f,String k,String id){for(Map<String,Object> r:rows(f,k))if(id.equals(r.get("id")))return r;return null;}
  static void check(boolean ok,String name){checks++;if(!ok)throw new AssertionError(name);}
  static Map<String,Object> empty(){return feed("2026-10-29T05:00:00Z",List.of(),List.of());}
  public static void main(String[] args){
    Map<String,Object> direct=feed("2026-10-29T05:00:00Z",List.of(source("water_kvu","2026-10-29T05:00:00Z"),source("max_water","2026-10-29T05:00:00Z")),List.of());
    Map<String,Object> baseline=feed("2026-10-29T09:45:00Z",List.of(source("water_kvu","2026-10-29T09:40:00Z")),List.of(kvu("new-water")));
    Map<String,Object> merged=NativeFeedMerge.merge(empty(),direct,baseline,NOW);
    check(row(merged,"events","new-water")!=null,"newer baseline imported despite delayed empty direct feed");
    check("2026-10-29T09:40:00Z".equals(row(merged,"sources","water_kvu").get("checkedAt")),"own source timestamp retained");
    check("2026-10-29T05:00:00Z".equals(row(merged,"sources","max_water").get("checkedAt")),"baseline cannot renew MAX");
    check("2026-10-29T05:00:00Z".equals(merged.get("cloudCheckedAt")),"cloud clock independent of newer baseline");
    check("2026-10-29T09:40:00Z".equals(row(merged,"events","new-water").get("lastConfirmedAt")),"confirmation uses source time, not refresh");
    check("2026-10-31T03:00:00Z".equals(row(merged,"events","new-water").get("retainUntil")),"36 hours after original announced end");
    merged.put("nativeCheckedAt","2026-10-29T10:00:00Z");merged.put("checkedAt","2026-10-29T10:00:00Z");
    Map<String,Object> offline=NativeFeedMerge.merge(merged,null,null,NOW.plusSeconds(3600));
    check("2026-10-29T05:00:00Z".equals(offline.get("cloudCheckedAt")),"cached native check never becomes cloud check");
    check("2026-10-29T09:40:00Z".equals(row(offline,"events","new-water").get("lastConfirmedAt")),"offline does not renew confirmation");
    check("unconfirmed".equals(row(offline,"events","new-water").get("status")),"cached event explicitly unconfirmed");
    check(Boolean.TRUE.equals(row(offline,"events","new-water").get("retained")),"cached event marked retained");
    Map<String,Object> noEvents=feed("2026-10-29T10:30:00Z",List.of(source("water_kvu","2026-10-29T10:30:00Z")),List.of());
    Map<String,Object> retained=NativeFeedMerge.merge(merged,null,noEvents,NOW.plusSeconds(3600));
    check(row(retained,"events","new-water")!=null,"empty response is not restoration");
    check("2026-10-29T09:40:00Z".equals(row(retained,"events","new-water").get("lastConfirmedAt")),"empty success does not renew event clock");
    check(rows(NativeFeedMerge.merge(merged,null,null,Instant.parse("2026-10-31T03:00:00Z")),"events").isEmpty(),"expiry at original end plus36h");
    Map<String,Object> failed=source("water_kvu","2026-10-29T09:50:00Z");failed.put("status","error");
    Map<String,Object> errorFeed=feed("2026-10-29T09:50:00Z",List.of(failed),List.of(kvu("bogus")));
    check(row(NativeFeedMerge.merge(empty(),null,errorFeed,NOW),"events","bogus")==null,"failed source cannot validate event");
    Map<String,Object> spoof=kvu("spoof");spoof.put("url","https://kvu.su.evil.example/utilities/x");
    Map<String,Object> spoofFeed=feed("2026-10-29T09:45:00Z",List.of(source("water_kvu","2026-10-29T09:40:00Z")),List.of(spoof));
    check(rows(NativeFeedMerge.merge(empty(),null,spoofFeed,NOW),"events").isEmpty(),"lookalike host rejected");
    Map<String,Object> injected=event("injected","max_water","official_max","https://max.ru/id6167110467_gos");
    Map<String,Object> hostile=feed("2026-10-29T09:45:00Z",List.of(source("max_water","2026-10-29T09:40:00Z")),List.of(injected));
    check(row(NativeFeedMerge.merge(empty(),direct,hostile,NOW),"events","injected")==null,"baseline cannot inject MAX event");
    check("2026-10-29T05:00:00Z".equals(row(NativeFeedMerge.merge(empty(),direct,hostile,NOW),"sources","max_water").get("checkedAt")),"baseline cannot replace MAX status");
    Map<String,Object> future=feed("2026-10-29T11:00:00Z",List.of(source("water_kvu","2026-10-29T11:00:00Z")),List.of(kvu("future")));
    check(rows(NativeFeedMerge.merge(empty(),null,future,NOW),"events").isEmpty(),"future source stamp rejected");
    Map<String,Object> stale=feed("2026-10-29T05:59:00Z",List.of(source("water_kvu","2026-10-29T05:59:00Z")),List.of(kvu("stale")));
    check(rows(NativeFeedMerge.merge(empty(),null,stale,NOW),"events").isEmpty(),"stale source cannot validate new event");
    Map<String,Object> restore=kvu("restoration");restore.put("status","resolved");restore.put("publishedAt","2026-10-29T09:00:00Z");
    Map<String,Object> restoredFeed=feed("2026-10-29T09:45:00Z",List.of(source("water_kvu","2026-10-29T09:40:00Z")),List.of(restore));
    Map<String,Object> restored=NativeFeedMerge.merge(merged,null,restoredFeed,NOW);
    check("resolved".equals(row(restored,"events","new-water").get("status")),"exact-address explicit restoration applied");
    check("resolved".equals(row(NativeFeedMerge.merge(restored,null,baseline,NOW),"events","new-water").get("status")),"old active publication cannot resurrect resolved event");
    restore.put("affected",List.of(map("street","ул Тестовая","houses",List.of("2"))));
    check(!"resolved".equals(row(NativeFeedMerge.merge(merged,null,restoredFeed,NOW),"events","new-water").get("status")),"different house cannot restore event");
    restore.put("affected",List.of());
    check(!"resolved".equals(row(NativeFeedMerge.merge(merged,null,restoredFeed,NOW),"events","new-water").get("status")),"missing coverage cannot restore event");
    Map<String,Object> partial=source("water_kvu","2026-10-29T09:40:00Z");partial.put("status","partial");partial.put("readStatus","ok");
    check(row(NativeFeedMerge.merge(empty(),null,feed("2026-10-29T09:45:00Z",List.of(partial),List.of(kvu("partial"))),NOW),"events","partial")!=null,"successful bounded reading accepted without complete coverage claim");
    Map<String,Object> noEnd=kvu("no-end");noEnd.remove("end");
    check("2026-10-30T19:00:00Z".equals(row(NativeFeedMerge.merge(empty(),null,feed("2026-10-29T09:45:00Z",List.of(partial),List.of(noEnd)),NOW),"events","no-end").get("retainUntil")),"missing end anchors to original start");
    Map<String,Object> deviceEvent=event("device","ursv_device","official_device","https://rovodokanal.ru/emergency-alerts/1");
    Map<String,Object> deviceSource=source("ursv_device",NOW.toString());deviceSource.put("status","partial");
    Map<String,Object> device=feed(NOW.toString(),List.of(deviceSource),List.of(deviceEvent));
    Map<String,Object> withDevice=NativeFeedMerge.merge(merged,direct,baseline,device,NOW);
    check(row(withDevice,"events","device")!=null,"actual partial device reading retained");
    check("active".equals(row(withDevice,"events","new-water").get("status")),"device merge does not mark fresh baseline unconfirmed");
    check("2026-10-29T05:00:00Z".equals(withDevice.get("cloudCheckedAt")),"device check does not renew direct cloud clock");
    deviceSource.put("status","error");device.put("events",List.of());
    Map<String,Object> lostDevice=NativeFeedMerge.merge(withDevice,null,null,device,NOW.plusSeconds(3600));
    check(row(lostDevice,"events","device")!=null,"device failure does not discard original notice");
    check("unconfirmed".equals(row(lostDevice,"events","device").get("status")),"failed device's retained notice unconfirmed");
    check("2026-10-29T10:00:00Z".equals(row(lostDevice,"events","device").get("lastConfirmedAt")),"device failure does not renew confirmation");
    Map<String,Object> archive=event("untrusted-archive","","official_archive","https://t.me/admshakhty/31053");archive.put("source","Шахтинский водоканал");
    Map<String,Object> archiveFeed=feed("2026-10-29T09:45:00Z",List.of(source("city","2026-10-29T09:40:00Z")),List.of(archive));
    check(rows(NativeFeedMerge.merge(empty(),null,archiveFeed,NOW),"events").isEmpty(),"mismatched official archive label rejected like frontend");
    archive.put("status","resolved");archive.put("publishedAt","2026-10-29T09:00:00Z");
    check(!"resolved".equals(row(NativeFeedMerge.merge(merged,null,archiveFeed,NOW),"events","new-water").get("status")),"untrusted archive cannot close legitimate event");
    injected.put("requiresReview",true);injected.put("status","resolved");injected.put("publishedAt","2026-10-29T09:00:00Z");
    check(row(NativeFeedMerge.merge(merged,hostile,null,NOW),"events","injected")==null,"MAX review-only record rejected");
    check(!"resolved".equals(row(NativeFeedMerge.merge(merged,hostile,null,NOW),"events","new-water").get("status")),"MAX review-only restoration cannot close legitimate event");
    Map<String,Object> saved=kvu("saved");saved.put("retained",true);saved.put("lastConfirmedAt","2026-10-29T08:00:00Z");saved.put("retainUntil","2026-10-31T03:00:00Z");
    Map<String,Object> savedFeed=feed("2026-10-29T09:45:00Z",List.of(source("water_kvu","2026-10-29T09:40:00Z")),List.of(saved));
    Map<String,Object> savedResult=NativeFeedMerge.merge(empty(),savedFeed,null,NOW);
    check("2026-10-29T08:00:00Z".equals(row(savedResult,"events","saved").get("lastConfirmedAt")),"incoming retained event does not inherit newer empty-source clock");
    check(Boolean.TRUE.equals(row(savedResult,"events","saved").get("retained")),"incoming retained flag preserved");
    check("unconfirmed".equals(row(savedResult,"events","saved").get("status")),"incoming retained event stays unconfirmed");
    rows(savedFeed,"sources").get(0).put("status","error");
    check(row(NativeFeedMerge.merge(empty(),savedFeed,null,NOW),"events","saved")!=null,"valid original retention proof survives failed source");
    saved.remove("lastConfirmedAt");
    check(rows(NativeFeedMerge.merge(empty(),savedFeed,null,NOW),"events").isEmpty(),"retained record without original proof rejected");
    Map<String,Object> weather=map("id","warning","category","mchs","sourceId","mchs","url","https://61.mchs.gov.ru/deyatelnost/press-centr/operativnaya-informaciya/1","status","active","start","2026-10-29T09:00:00Z","end","2026-10-29T11:00:00Z");
    Map<String,Object> weatherFeed=feed("2026-10-29T09:45:00Z",List.of(source("mchs","2026-10-29T09:40:00Z")),List.of(weather));
    Map<String,Object> warningResult=NativeFeedMerge.merge(empty(),weatherFeed,null,NOW);
    check(row(warningResult,"events","warning")!=null,"current warning preserved");
    check(rows(NativeFeedMerge.merge(warningResult,null,null,NOW.plusSeconds(7200)),"events").isEmpty(),"water36h policy never prolongs weather warning");
    Map<String,Object> power=event("power-max","max_power","official_max","https://max.ru/id6163089292_biz");power.put("category","power");
    Map<String,Object> powerFeed=feed("2026-10-29T09:45:00Z",List.of(source("max_power","2026-10-29T09:40:00Z")),List.of(power));
    Map<String,Object> powerSaved=NativeFeedMerge.merge(empty(),powerFeed,null,NOW);
    Map<String,Object> powerClosure=new LinkedHashMap<>(power);powerClosure.put("status","resolved");powerClosure.put("resolvedAt","2026-10-29T09:50:00Z");
    Map<String,Object> closureFeed=feed("2026-10-29T09:55:00Z",List.of(source("max_power","2026-10-29T09:55:00Z")),List.of());closureFeed.put("incidents",List.of(powerClosure));
    Map<String,Object> cloudClosed=NativeFeedMerge.merge(powerSaved,closureFeed,null,NOW);
    check("resolved".equals(row(cloudClosed,"events","power-max").get("status")),"cloud MAX power closure clears cached event immediately");
    check("resolved".equals(row(NativeFeedMerge.merge(cloudClosed,powerFeed,null,NOW),"events","power-max").get("status")),"older cloud MAX event cannot resurrect closure");
    Map<String,Object> baselineClosure=new LinkedHashMap<>(kvu("new-water"));baselineClosure.put("status","resolved");baselineClosure.put("resolvedAt","2026-10-29T09:50:00Z");
    Map<String,Object> baselineClosedFeed=feed("2026-10-29T09:55:00Z",List.of(source("water_kvu","2026-10-29T09:55:00Z")),List.of());baselineClosedFeed.put("incidents",List.of(baselineClosure));
    check("resolved".equals(row(NativeFeedMerge.merge(merged,null,baselineClosedFeed,NOW),"events","new-water").get("status")),"baseline closure clears cached event immediately");
    baselineClosure.put("resolvedAt","2026-10-29T11:00:00Z");
    check(!"resolved".equals(row(NativeFeedMerge.merge(merged,null,baselineClosedFeed,NOW),"events","new-water").get("status")),"future same-ID restoration cannot overwrite active incident");
    baselineClosure.put("resolvedAt","2026-10-29T09:50:00Z");baselineClosure.put("publishedAt","2026-10-29T11:00:00Z");
    check(!"resolved".equals(row(NativeFeedMerge.merge(merged,null,baselineClosedFeed,NOW),"events","new-water").get("status")),"future same-ID publication cannot overwrite active incident");
    baselineClosure.put("publishedAt","2026-10-29T09:50:00Z");baselineClosure.put("requiresReview",true);
    check(!"resolved".equals(row(NativeFeedMerge.merge(merged,null,baselineClosedFeed,NOW),"events","new-water").get("status")),"review-only same-ID restoration cannot overwrite active incident");
    baselineClosure.put("requiresReview",false);baselineClosure.put("resolvedAt","not-a-date");
    check(!"resolved".equals(row(NativeFeedMerge.merge(merged,null,baselineClosedFeed,NOW),"events","new-water").get("status")),"malformed explicit restoration date rejected");
    saved.put("lastConfirmedAt","2026-10-29T08:00:00Z");saved.remove("retainUntil");rows(savedFeed,"sources").get(0).put("status","ok");
    check(rows(NativeFeedMerge.merge(empty(),savedFeed,null,NOW),"events").isEmpty(),"fresh source cannot repair missing retained expiry proof");
    saved.put("retainUntil","2026-10-31T04:00:00Z");
    check(rows(NativeFeedMerge.merge(empty(),savedFeed,null,NOW),"events").isEmpty(),"fresh source cannot repair wrong retained expiry proof");
    Map<String,Object> legacyPower=event("legacy-power","power_repost","attributed_repost","https://news-don.ru/society/1.html");legacyPower.put("category","power");
    Map<String,Object> legacyFeed=feed("2026-10-29T09:45:00Z",List.of(source("power_repost_don","2026-10-29T09:40:00Z"),source("power_repost_rostov","2026-10-29T09:40:00Z")),List.of(legacyPower));
    check(row(NativeFeedMerge.merge(empty(),legacyFeed,null,NOW),"events","legacy-power")!=null,"legacy generic power ID maps to exact Don mirror source");
    legacyPower.put("url","https://newsrostov.ru/society/1.html");
    check(row(NativeFeedMerge.merge(empty(),legacyFeed,null,NOW),"events","legacy-power")!=null,"legacy generic power ID maps to exact Rostov mirror source");
    legacyPower.put("url","https://news-don.ru.evil.example/society/1.html");
    check(rows(NativeFeedMerge.merge(empty(),legacyFeed,null,NOW),"events").isEmpty(),"generic power ID never permits lookalike host");
    legacyPower.put("url","https://news-don.ru/society/1.html");legacyPower.put("sourceId","power_repost_rostov");
    check(rows(NativeFeedMerge.merge(empty(),legacyFeed,null,NOW),"events").isEmpty(),"specific power source mismatching mirror rejected");
    legacyPower.remove("sourceId");
    check(rows(NativeFeedMerge.merge(empty(),legacyFeed,null,NOW),"events").isEmpty(),"missing power source ID rejected like frontend");
    check(!baseline.containsKey("cloudCheckedAt")&&!kvu("x").containsKey("lastConfirmedAt"),"input feed not mutated");
    System.out.println("NATIVE FEED MERGE CHECKS PASSED: "+checks);
  }
}
