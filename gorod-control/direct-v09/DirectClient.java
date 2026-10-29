package ru.citycontrol.shakhty;

import android.content.Context;
import android.text.Html;
import android.util.AtomicFile;
import org.json.*;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.time.*;
import java.util.*;
import java.util.regex.*;

/** Original URSV pages are read from the user's network, not an overseas scraping proxy. */
public final class DirectClient {
  public static final String FEED="https://27andrej1976-afk.github.io/maximum-shakhty-admin/gorod-control/direct-v09/feed.json";
  public static final String BASELINE="https://27andrej1976-afk.github.io/maximum-shakhty-admin/gorod-control/data/water.json";
  public static final String URSV="https://rovodokanal.ru/emergency-alerts/";
  private static final int MAX_BYTES=2200000;
  private static final class Net {int status;String body;Net(int s,String b){status=s;body=b;}}
  private static Pattern re(String p){return Pattern.compile(p,Pattern.CASE_INSENSITIVE|Pattern.UNICODE_CASE|Pattern.DOTALL);}
  private static Net read(String address,String allowedHost) throws Exception {
    URL u=new URL(address);
    for(int redirects=0;redirects<3;redirects++){
      if(!u.getProtocol().equals("https")||!u.getHost().equals(allowedHost)||u.getUserInfo()!=null)throw new IOException("Недопустимое перенаправление");
      HttpURLConnection c=(HttpURLConnection)u.openConnection();c.setInstanceFollowRedirects(false);
      c.setConnectTimeout(10000);c.setReadTimeout(12000);c.setRequestProperty("User-Agent","CityControlShakhty/0.9 Android public notices");
      c.setRequestProperty("Accept","text/html,application/json");c.setRequestProperty("Cache-Control","no-cache");
      try{
        int status=c.getResponseCode();
        if(status>=300&&status<400){String target=c.getHeaderField("Location");if(target==null)throw new IOException("Пустое перенаправление");u=new URL(u,target);continue;}
        if(status!=200)return new Net(status,"");
        try(InputStream in=c.getInputStream();ByteArrayOutputStream bytes=new ByteArrayOutputStream()){
          byte[] b=new byte[8192];int n;while((n=in.read(b))!=-1){if(bytes.size()+n>MAX_BYTES)throw new IOException("Слишком большой ответ");bytes.write(b,0,n);}
          return new Net(status,bytes.toString("UTF-8"));
        }
      }finally{c.disconnect();}
    }
    throw new IOException("Слишком много перенаправлений");
  }
  private static AtomicFile cache(Context c){return new AtomicFile(new File(c.getFilesDir(),"city-feed-v09.json"));}
  public static JSONObject cached(Context c){
    try(InputStream in=cache(c).openRead()){return new JSONObject(new String(readBounded(in),StandardCharsets.UTF_8));}
    catch(Exception e){try(InputStream in=c.getAssets().open("web/data/feed-snapshot.json")){JSONObject d=new JSONObject(new String(readBounded(in),StandardCharsets.UTF_8));d.put("cached",true);return d;}catch(Exception x){return new JSONObject();}}
  }
  private static byte[] readBounded(InputStream in) throws IOException {
    ByteArrayOutputStream out=new ByteArrayOutputStream();byte[] b=new byte[8192];int n;
    while((n=in.read(b))!=-1){if(out.size()+n>MAX_BYTES)throw new IOException("Cache overflow");out.write(b,0,n);}return out.toByteArray();
  }
  private static void save(Context c,JSONObject data){
    AtomicFile f=cache(c);FileOutputStream out=null;
    try{out=f.startWrite();out.write(data.toString().getBytes(StandardCharsets.UTF_8));f.finishWrite(out);}catch(Exception e){if(out!=null)f.failWrite(out);}
  }
  private static long millis(String value){try{return OffsetDateTime.parse(value).toInstant().toEpochMilli();}catch(Exception e){return 0;}}
  public static String plain(String html){
    String s=re("<(script|style|nav|header|footer)[^>]*>.*?</\\1>").matcher(html).replaceAll("");
    s=re("</?(?:p|div|li|h[1-6]|tr|br)[^>]*>").matcher(s).replaceAll("<br>");
    return Html.fromHtml(s,Html.FROM_HTML_MODE_LEGACY).toString().replace('\u00a0',' ').replaceAll("\\n[ \\t]*\\n+","\n").trim();
  }
  private static String published(String html){
    Matcher time=re("<time[^>]*datetime=[\"']([^\"']+)[\"']").matcher(html);if(time.find())return time.group(1);
    Matcher meta=re("<meta[^>]*(?:property|name)=[\"']article:published_time[\"'][^>]*content=[\"']([^\"']+)[\"']").matcher(html);
    return meta.find()?meta.group(1):null;
  }
  private static Map<String,Object> objectMap(JSONObject object) throws JSONException {
    Map<String,Object> out=new LinkedHashMap<>();
    for(Iterator<String> it=object.keys();it.hasNext();){String key=it.next();out.put(key,jsonValue(object.get(key)));}return out;
  }
  private static Object jsonValue(Object value) throws JSONException {
    if(value==JSONObject.NULL)return null;
    if(value instanceof JSONObject)return objectMap((JSONObject)value);
    if(value instanceof JSONArray){List<Object> out=new ArrayList<>();JSONArray array=(JSONArray)value;for(int i=0;i<array.length();i++)out.add(jsonValue(array.get(i)));return out;}
    return value;
  }
  private static JSONObject readFeed(String url,long requestTime) throws Exception {
    Net r=read(url+"?_="+requestTime,"27andrej1976-afk.github.io");if(r.status!=200)throw new IOException("HTTP "+r.status);
    JSONObject feed=new JSONObject(r.body);
    if(feed.optInt("schema")!=2||feed.optJSONArray("events")==null||feed.optJSONArray("sources")==null)throw new IOException("Формат облачной сводки изменён");
    return feed;
  }
  public static synchronized JSONObject refresh(Context ctx){
    Instant now=Instant.now();JSONObject data=cached(ctx),cloud=null,baseline=null;boolean cloudRead=false,baselineRead=false;String cloudError=null,baselineError=null;
    try{cloud=readFeed(FEED,now.toEpochMilli());cloudRead=true;}
    catch(Exception e){cloudError=e.getClass().getSimpleName()+": "+e.getMessage();}
    // The municipal feed has an independent schedule. A delayed direct/MAX job must not hide newer notices.
    try{baseline=readFeed(BASELINE,now.toEpochMilli());baselineRead=true;}
    catch(Exception e){baselineError=e.getClass().getSimpleName()+": "+e.getMessage();}
    try{
      JSONObject water=new JSONObject();water.put("id","ursv_device");water.put("url",URSV);water.put("transport","device_direct_https");water.put("checkedAt",now.toString());water.put("posts",0);water.put("status","error");
      int fetched=0,accepted=0,failed=0;JSONArray direct=new JSONArray();
      try{
        Net index=read(URSV,"rovodokanal.ru");water.put("httpStatus",index.status);
        if(index.status!=200)throw new IOException("HTTP "+index.status+(index.status==403?" — сайт ограничил доступ из этой сети":""));
        Matcher links=re("<a\\b[^>]*href=[\"']((?:https://rovodokanal\\.ru)?/emergency-alerts/\\d+)[\"']").matcher(index.body);
        TreeSet<Integer> ids=new TreeSet<>(Collections.reverseOrder());while(links.find())try{String v=links.group(1);ids.add(Integer.parseInt(v.substring(v.lastIndexOf('/')+1)));}catch(Exception ignored){}
        if(ids.isEmpty())throw new IOException("Страница открылась, но ссылки на объявления не распознаны");
        water.put("listedPosts",ids.size());
        long deadline=System.currentTimeMillis()+42000L;
        for(Integer id:ids){if(fetched>=8||System.currentTimeMillis()>deadline)break;fetched++;
          String url=URSV+id;
          try{Net page=read(url,"rovodokanal.ru");if(page.status!=200){failed++;continue;}
            Map<String,Object> parsed=WaterNotice.parse(url,plain(page.body),now,published(page.body));
            if(parsed!=null){direct.put(new JSONObject(parsed));accepted++;}
          }catch(Exception e){failed++;}
        }
        water.put("posts",fetched);water.put("matchingPosts",accepted);water.put("failedPosts",failed);
        water.put("status",accepted>0&&failed==0?"ok":"partial");
        water.put("note",accepted>0?"Оригиналы УРСВ получены с телефона. Проверена ограниченная часть ленты; это не полный перечень аварий.":"Сайт прочитан, но свежие адресные объявления Шахт не распознаны. Полнота не подтверждена.");
      }catch(Exception e){water.put("note","Прямое чтение УРСВ не подтверждено: "+e.getMessage());}
      Map<String,Object> device=new LinkedHashMap<>();device.put("checkedAt",now.toString());device.put("sources",Arrays.asList(objectMap(water)));
      device.put("events",jsonValue(direct));
      data=new JSONObject(NativeFeedMerge.merge(objectMap(data),cloud==null?null:objectMap(cloud),baseline==null?null:objectMap(baseline),device,now));
      JSONArray src=data.getJSONArray("sources");
      for(int i=0;i<src.length();i++){
        JSONObject source=src.getJSONObject(i);long checked=millis(source.optString("checkedAt",""));
        if(checked==0||now.toEpochMilli()-checked>4*3600000L||checked>now.toEpochMilli()+120000)source.put("status","stale");
      }
      data.put("checkedAt",now.toString());data.put("nativeCheckedAt",now.toString());data.put("cloudOnline",cloudRead);data.put("baselineOnline",baselineRead);
      data.put("cloudError",cloudError==null?JSONObject.NULL:cloudError);data.put("baselineError",baselineError==null?JSONObject.NULL:baselineError);
      data.put("cached",!(cloudRead||baselineRead));data.put("coverage","partial");
      save(ctx,data);
    }catch(Exception ignored){}
    return data;
  }
}
