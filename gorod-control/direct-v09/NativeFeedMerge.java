package ru.citycontrol.shakhty;

import java.time.*;
import java.util.*;

/** Pure, offline merge policy. Checking a cached feed never renews source/event clocks. */
public final class NativeFeedMerge {
  private static final long RETAIN_MS=36L*3600000, FRESH_MS=4L*3600000;
  private static final Set<String> BASELINE=new HashSet<>(Arrays.asList(
      "city","water_kvu","repost_rostov","repost_don","power_repost_rostov",
      "power_repost_don","power_city","gas_city","gas","mchs"));
  private static final Set<String> CLOSED=new HashSet<>(Arrays.asList("resolved","cancelled","canceled"));
  private NativeFeedMerge(){}
  static String str(Map<String,Object> x,String k){Object v=x.get(k);return v instanceof String?(String)v:"";}
  static long time(String x){try{return OffsetDateTime.parse(x).toInstant().toEpochMilli();}catch(Exception ignored){return 0;}}
  @SuppressWarnings("unchecked") static List<Map<String,Object>> rows(Map<String,Object> x,String k){
    List<Map<String,Object>> out=new ArrayList<>();Object a=x.get(k);
    if(a instanceof List<?>)for(Object v:(List<?>)a)if(v instanceof Map<?,?>)out.add((Map<String,Object>)v);
    return out;
  }
  @SuppressWarnings("unchecked") static Object copy(Object x){
    if(x instanceof Map<?,?>){Map<String,Object> out=new LinkedHashMap<>();((Map<String,Object>)x).forEach((k,v)->out.put(k,copy(v)));return out;}
    if(x instanceof List<?>){List<Object> out=new ArrayList<>();for(Object v:(List<?>)x)out.add(copy(v));return out;}
    return x;
  }
  @SuppressWarnings("unchecked") static Map<String,Object> duplicate(Map<String,Object> x){return (Map<String,Object>)copy(x);}
  public static String cloudStamp(Map<String,Object> x){
    // Legacy native snapshots used checkedAt for the device run, not for the cloud feed.
    if(x.containsKey("nativeCheckedAt"))return str(x,"cloudCheckedAt");
    return str(x,"checkedAt");
  }
  private static Map<String,Map<String,Object>> sources(Map<String,Object> feed,boolean baseline){
    Map<String,Map<String,Object>> out=new LinkedHashMap<>();
    for(Map<String,Object> row:rows(feed,"sources")){
      String id=str(row,"id");if(id.isEmpty()||baseline&&!BASELINE.contains(id))continue;
      Map<String,Object> item=duplicate(row);
      if(str(item,"checkedAt").isEmpty())item.put("checkedAt",baseline?str(feed,"checkedAt"):cloudStamp(feed));
      out.put(id,item);
    }
    return out;
  }
  private static boolean fresh(Map<String,Object> s,long now,String sid){
    if(s==null)return false;
    long checked=time(str(s,"checkedAt")),age=now-checked;
    boolean read="ok".equals(str(s,"status"))||"ok".equals(str(s,"readStatus"))
        ||"ursv_device".equals(sid)&&"partial".equals(str(s,"status"));
    return read&&checked>0&&age>=-120000&&age<FRESH_MS;
  }
  private static boolean at(String url,String host,String prefix){
    try{java.net.URI u=new java.net.URI(url);return "https".equals(u.getScheme())&&host.equals(u.getHost())&&u.getUserInfo()==null&&(u.getPort()==-1||u.getPort()==443)&&u.getPath().startsWith(prefix);}catch(Exception ignored){return false;}
  }
  /** Exact origin/category/URL association; a label alone cannot make a source trusted. */
  static String sourceId(Map<String,Object> e){
    String category=str(e,"category"),origin=str(e,"origin"),sid=str(e,"sourceId"),url=str(e,"url");
    if("water".equals(category)){
      if("official_device".equals(origin)&&"ursv_device".equals(sid)&&url.matches("^https://rovodokanal\\.ru/emergency-alerts/\\d+$"))return sid;
      if("media_report".equals(origin)&&"water_kvu".equals(sid)&&at(url,"kvu.su","/utilities/"))return sid;
      String mirror=at(url,"news-don.ru","/")?"repost_don":at(url,"newsrostov.ru","/")?"repost_rostov":"";
      if("municipal_repost".equals(origin)&&!mirror.isEmpty()&&mirror.equals(sid))return sid;
      if("verified_repost".equals(origin)&&!mirror.isEmpty()&&(sid.isEmpty()||sid.equals(mirror))&&str(e,"officialUrl").matches("^https://rovodokanal\\.ru/emergency-alerts/\\d+$"))return mirror;
      if("Администрация города Шахты".equals(str(e,"source"))&&(sid.isEmpty()||"city".equals(sid))&&url.matches("^https://t\\.me/admshakhty/\\d+$"))return "city";
      if("official_max".equals(origin)&&!Boolean.TRUE.equals(e.get("requiresReview"))&&(("max_city".equals(sid)&&url.equals("https://max.ru/shakhtygorod"))||("max_water".equals(sid)&&url.equals("https://max.ru/id6167110467_gos"))))return sid;
    }
    if("power".equals(category)){
      if("official_site".equals(origin)&&"power_direct".equals(sid)&&url.equals("https://donenergo.ru/grafik-otklyucheniy/61/1/"))return sid;
      if("official_city_post".equals(origin)&&"power_city".equals(sid)&&url.matches("^https://t\\.me/admshakhty/\\d+$"))return sid;
      if("attributed_repost".equals(origin)){
        if(at(url,"news-don.ru","/")&&(sid.equals("power_repost")||sid.equals("power_repost_don")))return "power_repost_don";
        if(at(url,"newsrostov.ru","/")&&(sid.equals("power_repost")||sid.equals("power_repost_rostov")))return "power_repost_rostov";
      }
      if("official_max".equals(origin)&&!Boolean.TRUE.equals(e.get("requiresReview"))&&(("max_city".equals(sid)&&url.equals("https://max.ru/shakhtygorod"))||("max_power".equals(sid)&&url.equals("https://max.ru/id6163089292_biz"))))return sid;
    }
    if("gas".equals(category)&&"official_city_post".equals(origin)&&"gas_city".equals(sid)&&url.matches("^https://t\\.me/admshakhty/\\d+$"))return sid;
    if("mchs".equals(category)&&"mchs".equals(sid)&&at(url,"61.mchs.gov.ru","/deyatelnost/press-centr/operativnaya-informaciya/"))return sid;
    return "";
  }
  private static long deadline(Map<String,Object> e){
    for(String field:Arrays.asList("end","start","publishedAt","observedAt")){long t=time(str(e,field));if(t>0)return t+RETAIN_MS;}
    return 0;
  }
  private static boolean validClosure(Map<String,Object> e,long now){
    if(!CLOSED.contains(str(e,"status")))return true;
    if(Boolean.TRUE.equals(e.get("requiresReview"))||Boolean.TRUE.equals(e.get("reviewRequired")))return false;
    boolean dated=false;
    for(String field:Arrays.asList("resolvedAt","publishedAt")){
      String value=str(e,field);if(value.isEmpty())continue;
      long stamp=time(value);if(stamp==0||stamp>now)return false;dated=true;
    }
    return dated;
  }
  private static List<String> areas(Map<String,Object> e){
    List<String> out=new ArrayList<>();
    for(Map<String,Object> a:rows(e,"affected")){
      String street=str(a,"street").trim().toLowerCase(Locale.ROOT);if(street.isEmpty())continue;
      List<String> houses=new ArrayList<>();Object h=a.get("houses");if(h instanceof List<?>)for(Object v:(List<?>)h)houses.add(String.valueOf(v));Collections.sort(houses);
      out.add(street+"|"+houses.toString());
    }
    Collections.sort(out);return out;
  }
  private static void ingest(Map<String,Object> feed,boolean baseline,Map<String,Map<String,Object>> states,
      Map<String,Map<String,Object>> events,Set<String> freshIds,long now){
    Map<String,Map<String,Object>> own=sources(feed,baseline);
    for(Map.Entry<String,Map<String,Object>> entry:own.entrySet()){
      Map<String,Object> prior=states.get(entry.getKey());long stamp=time(str(entry.getValue(),"checkedAt"));
      if(stamp>0&&stamp<=now+120000&&(prior==null||stamp>=time(str(prior,"checkedAt"))))states.put(entry.getKey(),entry.getValue());
    }
    List<Map<String,Object>> incoming=new ArrayList<>(rows(feed,"events"));
    // Both collectors retain validated closures outside the visible event list.
    for(Map<String,Object> e:rows(feed,"incidents"))if(CLOSED.contains(str(e,"status")))incoming.add(e);
    for(Map<String,Object> input:incoming){
      String sid=sourceId(input),id=str(input,"id");Map<String,Object> source=own.get(sid);
      long proof=time(str(input,"lastConfirmedAt")),until=deadline(input);
      boolean retainedProof=proof>0&&proof<=now+120000&&proof<=until&&until>now&&time(str(input,"retainUntil"))==until;
      if(id.isEmpty()||sid.isEmpty()||baseline&&!BASELINE.contains(sid)||source==null||!fresh(source,now,sid)&&!retainedProof)continue;
      if(Boolean.TRUE.equals(input.get("retained"))&&!retainedProof||!validClosure(input,now))continue;
      Map<String,Object> previous=events.get(id);
      String confirmation=str(input,"lastConfirmedAt");
      // A collector may return retained items beside a newer successful empty source check.
      // Preserve the event-level evidence clock; never turn that new check into confirmation.
      if(confirmation.isEmpty()&&!Boolean.TRUE.equals(input.get("retained")))confirmation=str(source,"checkedAt");
      long confirmed=time(confirmation);
      if(confirmed==0||confirmed>now+120000||confirmed>deadline(input))continue;
      if(previous!=null&&(CLOSED.contains(str(previous,"status"))&&!CLOSED.contains(str(input,"status"))||confirmed<time(str(previous,"lastConfirmedAt"))))continue;
      Map<String,Object> e=duplicate(input);e.put("lastConfirmedAt",confirmation);events.put(id,e);
      if(!Boolean.TRUE.equals(input.get("retained"))&&fresh(source,now,sid))freshIds.add(id);
    }
  }
  public static Map<String,Object> merge(Map<String,Object> cached,Map<String,Object> cloud,Map<String,Object> baseline,Instant instant){
    return merge(cached,cloud,baseline,null,instant);
  }
  public static Map<String,Object> merge(Map<String,Object> cached,Map<String,Object> cloud,Map<String,Object> baseline,Map<String,Object> device,Instant instant){
    long now=instant.toEpochMilli();Map<String,Object> result=duplicate(cloud==null?cached:cloud);
    Map<String,Map<String,Object>> states=sources(cached,false),events=new LinkedHashMap<>();Set<String> freshIds=new HashSet<>();
    for(Map<String,Object> input:rows(cached,"events")){
      String sid=sourceId(input),id=str(input,"id");if(sid.isEmpty()||id.isEmpty()||!validClosure(input,now))continue;
      Map<String,Object> e=duplicate(input);
      if(str(e,"lastConfirmedAt").isEmpty()&&fresh(states.get(sid),now,sid))e.put("lastConfirmedAt",str(states.get(sid),"checkedAt"));
      events.put(id,e);
    }
    if(cloud!=null)ingest(cloud,false,states,events,freshIds,now);
    if(baseline!=null)ingest(baseline,true,states,events,freshIds,now);
    if(device!=null)ingest(device,false,states,events,freshIds,now);
    // Never infer restoration from an empty list, failed request, refresh time, or fuzzy location.
    for(Map<String,Object> r:events.values())if("resolved".equals(str(r,"status"))){
      if(Boolean.TRUE.equals(r.get("requiresReview"))||Boolean.TRUE.equals(r.get("reviewRequired")))continue;
      long when=time(str(r,"resolvedAt"));
      // A normalized incident's publishedAt is the outage publication, not its restoration.
      if(when==0&&(!r.containsKey("noticeId")||"resolved".equals(str(r,"kind"))))when=time(str(r,"publishedAt"));
      if(when==0||when>now)continue;
      List<Map<String,Object>> matches=new ArrayList<>();List<String> coverage=areas(r);String site=str(r,"workSite");
      for(Map<String,Object> e:events.values()){
        long started=time(str(e,"start"));if(started==0)started=time(str(e,"publishedAt"));
        if(CLOSED.contains(str(e,"status"))||!str(r,"category").equals(str(e,"category"))||started==0||started>when)continue;
        boolean equal=!coverage.isEmpty()&&coverage.equals(areas(e));
        if(!site.isEmpty()?site.equals(str(e,"workSite"))&&(coverage.isEmpty()||equal):equal)matches.add(e);
      }
      if(matches.size()==1){Map<String,Object> e=matches.get(0);e.put("status","resolved");e.put("resolvedAt",Instant.ofEpochMilli(when).toString());e.put("resolutionUrl",str(r,"url"));}
    }
    List<Map<String,Object>> kept=new ArrayList<>();
    for(Map<String,Object> e:events.values()){
      boolean retained=!freshIds.contains(str(e,"id"));long until=deadline(e),confirmed=time(str(e,"lastConfirmedAt"));
      if(!Arrays.asList("water","power").contains(str(e,"category"))){
        // The 36-hour outage policy does not prolong weather warnings or gas notices.
        long end=time(str(e,"end"));
        if(!retained&&!CLOSED.contains(str(e,"status"))&&(end==0||end>now))kept.add(e);
        continue;
      }
      if(until<=now||confirmed==0||confirmed>now+120000||confirmed>until)continue;
      e.put("retainUntil",Instant.ofEpochMilli(until).toString());e.put("retained",retained);
      if(!CLOSED.contains(str(e,"status"))&&(retained||time(str(e,"end"))>0&&time(str(e,"end"))<now))e.put("status","unconfirmed");
      kept.add(e);
    }
    result.put("schema",2);result.put("sources",new ArrayList<>(states.values()));result.put("events",kept);
    result.put("cloudCheckedAt",cloud==null?cloudStamp(cached):cloudStamp(cloud));
    String baselineStamp=baseline==null?str(cached,"baselineCheckedAt"):str(baseline,"checkedAt");
    result.put("baselineCheckedAt",baselineStamp);return result;
  }
}
