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
      c.setRequestProperty("Accept","text/html,application/json");
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
  public static synchronized JSONObject refresh(Context ctx){
    Instant now=Instant.now();JSONObject data=cached(ctx);boolean cloudRead=false;String cloudError=null;
    try{Net r=read(FEED,"27andrej1976-afk.github.io");if(r.status!=200)throw new IOException("HTTP "+r.status);
      JSONObject fresh=new JSONObject(r.body);if(fresh.optInt("schema")!=2||fresh.optJSONArray("events")==null||fresh.optJSONArray("sources")==null)throw new IOException("Формат облачной сводки изменён");data=fresh;cloudRead=true;
    }catch(Exception e){cloudError=e.getClass().getSimpleName()+": "+e.getMessage();}
    try{
      JSONArray src=new JSONArray(),events=new JSONArray();String cloudStamp=data.optString("checkedAt","");
      JSONArray oldSrc=data.optJSONArray("sources");if(oldSrc!=null)for(int i=0;i<oldSrc.length();i++){
        JSONObject s=oldSrc.optJSONObject(i);if(s==null||s.optString("id").equals("ursv_device"))continue;
        if(!s.has("checkedAt"))s.put("checkedAt",cloudStamp);
        long checked=millis(s.optString("checkedAt",""));if(checked==0||now.toEpochMilli()-checked>4*3600000L)s.put("status","stale");src.put(s);
      }
      JSONArray oldEvents=data.optJSONArray("events");if(oldEvents!=null)for(int i=0;i<oldEvents.length();i++){
        JSONObject e=oldEvents.optJSONObject(i);if(e!=null&&!e.optString("sourceId").equals("ursv_device"))events.put(e);
      }
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
      Set<String> originalIds=new HashSet<>();for(int i=0;i<direct.length();i++)originalIds.add(direct.getJSONObject(i).optString("id"));
      JSONArray combined=new JSONArray();for(int i=0;i<events.length();i++){JSONObject e=events.getJSONObject(i);if(!originalIds.contains(e.optString("id")))combined.put(e);}
      for(int i=0;i<direct.length();i++)combined.put(direct.getJSONObject(i));src.put(water);
      data.put("schema",2);data.put("events",combined);data.put("sources",src);data.put("cloudCheckedAt",cloudStamp);
      data.put("checkedAt",now.toString());data.put("nativeCheckedAt",now.toString());data.put("cloudOnline",cloudRead);
      data.put("cloudError",cloudError==null?JSONObject.NULL:cloudError);data.put("cached",!cloudRead);data.put("coverage","partial");
      save(ctx,data);
    }catch(Exception ignored){}
    return data;
  }
}
