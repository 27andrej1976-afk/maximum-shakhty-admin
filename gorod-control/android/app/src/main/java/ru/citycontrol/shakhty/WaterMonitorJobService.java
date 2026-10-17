package ru.citycontrol.shakhty;

import android.Manifest;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.job.JobParameters;
import android.app.job.JobService;
import android.content.Intent;
import android.content.Context;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.os.Build;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.time.OffsetDateTime;
import java.util.Locale;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public final class WaterMonitorJobService extends JobService {
  public static final int JOB_ID=71603;
  private static final String DATA_URL="https://27andrej1976-afk.github.io/maximum-shakhty-admin/gorod-control/data/water.json";
  private static final String CHANNEL="city_control_water";
  private volatile boolean stopped=false;
  private Thread task;

  @Override public boolean onStartJob(JobParameters params) {
    stopped=false;
    task=new Thread(() -> {
      try{ checkCurrentWaterNotices(); }
      catch(Exception ignored){ /* Never notify from unverified, failed or stale data */ }
      finally{jobFinished(params,false);}
    },"WaterNotices");
    task.start();
    return true;
  }
  @Override public boolean onStopJob(JobParameters params) {
    stopped=true;
    if(task!=null)task.interrupt();
    return true;
  }

  private void checkCurrentWaterNotices() throws Exception {
    SharedPreferences prefs=getSharedPreferences("city-control-home",MODE_PRIVATE);
    String street=canonicalStreet(prefs.getString("street",""));
    String house=canonicalHouse(prefs.getString("house",""));
    if(street.isEmpty()||stopped)return;
    if(Build.VERSION.SDK_INT>=33 && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)!=PackageManager.PERMISSION_GRANTED) return;

    HttpURLConnection conn=(HttpURLConnection)new URL(DATA_URL+"?t="+(System.currentTimeMillis()/600000L)).openConnection();
    conn.setConnectTimeout(14000);conn.setReadTimeout(14000);conn.setRequestProperty("Accept","application/json");
    StringBuilder raw=new StringBuilder();
    try{
      if(conn.getResponseCode()!=200)return;
      try(BufferedReader rd=new BufferedReader(new InputStreamReader(conn.getInputStream(),StandardCharsets.UTF_8))){
        String line;
        while((line=rd.readLine())!=null && raw.length()<250000)raw.append(line);
      }
    }finally{conn.disconnect();}
    JSONObject data=new JSONObject(raw.toString());
    if(data.optInt("schema",0)!=2)return;
    long now=System.currentTimeMillis();
    long lastScan=utcMillis(data.optString("checkedAt",""));
    if(lastScan<=0||now-lastScan>4L*3600000||lastScan-now>20L*60000)return;
    JSONArray sources=data.optJSONArray("sources");
    if(sources==null)return;
    boolean sourceAvailable=false;
    for(int j=0;j<sources.length();j++){
      JSONObject s=sources.optJSONObject(j);
      if(s==null||!"ok".equals(s.optString("status")))continue;
      String id=s.optString("id","");
      if(id.equals("water")||id.equals("city")||id.startsWith("repost_")) sourceAvailable=true;
    }
    if(!sourceAvailable)return;
    JSONArray events=data.optJSONArray("events");
    if(events==null)return;
    for(int i=0;i<events.length()&&!stopped;i++){
      JSONObject e=events.optJSONObject(i);
      if(e==null||!"active".equals(e.optString("status")))continue;
      String eventId=e.optString("id","");
      String kind=e.optString("kind","");
      if(eventId.isEmpty()||!(kind.equals("planned")||kind.equals("emergency")))continue;
      String origin=e.optString("origin","");
      if(origin.equals("verified_repost") &&
        !e.optString("officialUrl","").matches("^https://rovodokanal\\.ru/emergency-alerts/\\d+$"))continue;
      if(!origin.equals("verified_repost") && !(
           e.optString("source","").equals("Шахтинский водоканал")||
           e.optString("source","").equals("Администрация города Шахты"))) continue;

      long start=utcMillis(e.optString("start",""));
      long end=utcMillis(e.optString("end",""));
      if(start<=0)continue;
      if(start>now+14L*86400000)continue;
      if(end>0&&end<now)continue;
      if(kind.equals("emergency") && start<now-48L*3600000)continue;
      Match match=affectedHouse(e.optJSONArray("affected"),street,house);
      if(match==Match.NONE)continue;
      String key="water-alert:"+eventId+":"+e.optString("start","");
      if(prefs.getBoolean(key,false))continue;
      issueNotification(eventId,kind,match,e.optString("start",""),e.optString("title",""));
      prefs.edit().putBoolean(key,true).apply();
    }
  }
  private enum Match { NONE, STREET, EXACT }
  private Match affectedHouse(JSONArray areas,String homeStreet,String homeHouse){
    if(areas==null)return Match.NONE;
    Match outcome=Match.NONE;
    for(int i=0;i<areas.length();i++){
      JSONObject a=areas.optJSONObject(i);
      if(a==null||!canonicalStreet(a.optString("street","")).equals(homeStreet))continue;
      JSONArray houses=a.optJSONArray("houses");
      if(houses==null||houses.length()==0) outcome=Match.STREET;
      else if(!homeHouse.isEmpty()){
        for(int j=0;j<houses.length();j++){
          if(matchesHouse(homeHouse,houses.optString(j)))return Match.EXACT;
        }
      }
    }
    return outcome;
  }
  private static boolean matchesHouse(String home,String listed){
    String t=canonicalHouse(listed);
    if(home.equals(t))return true;
    Matcher range=Pattern.compile("^(\\d+)-(\\d+)$").matcher(t);
    Matcher homeNumber=Pattern.compile("^(\\d+)").matcher(home);
    if(!range.matches()||!homeNumber.find())return false;
    try{
      int a=Integer.parseInt(range.group(1)),b=Integer.parseInt(range.group(2)),n=Integer.parseInt(homeNumber.group(1));
      return n>=Math.min(a,b)&&n<=Math.max(a,b)&&(a%2!=b%2||n%2==a%2);
    }catch(NumberFormatException e){return false;}
  }
  private static String canonicalHouse(String s){
    return s.toLowerCase(Locale.ROOT).replace('ё','е')
      .replaceFirst("^(?:д(?:ом)?\\.?\\s*)","").replaceAll("\\s+","").replaceAll("[^\\da-zа-я/\\-]","");
  }
  private static String canonicalStreet(String s){
    return s.toLowerCase(Locale.ROOT).replace('ё','е').trim()
      .replaceFirst("^(?:г\\.?\\s*шахты\\s*,?\\s*)?","")
      .replaceFirst("^(?:ул(?:ица)?|пер(?:еулок)?|проспект|пр-?кт|пр-?т|пр-?д|проезд|пл(?:ощадь)?|мкр|пос(?:елок)?|п)\\.?\\s+","")
      .replaceAll("\\s+"," ").replaceAll("[.,;]+$","").trim();
  }
  private static long utcMillis(String stamp){
    try{return OffsetDateTime.parse(stamp).toInstant().toEpochMilli();}
    catch(Exception e){return 0;}
  }
  /** Device-only test message. Never pretends to be a real incident. */
  public static boolean showTestNotification(Context context) {
    if(Build.VERSION.SDK_INT>=33 &&
      context.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)!=PackageManager.PERMISSION_GRANTED) return false;
    NotificationManager manager=(NotificationManager)context.getSystemService(Context.NOTIFICATION_SERVICE);
    if(manager==null)return false;
    NotificationChannel channel=new NotificationChannel(CHANNEL,
       "Вода — коммунальные предупреждения",NotificationManager.IMPORTANCE_DEFAULT);
    manager.createNotificationChannel(channel);
    Intent intent=new Intent(context,MainActivity.class);
    PendingIntent tap=PendingIntent.getActivity(context,100100,intent,
        PendingIntent.FLAG_IMMUTABLE|PendingIntent.FLAG_UPDATE_CURRENT);
    Notification notice=new Notification.Builder(context,CHANNEL)
       .setSmallIcon(android.R.drawable.stat_notify_error)
       .setContentTitle("ТЕСТ: уведомления работают")
       .setContentText("Это проверка телефона. Никаких аварий данное уведомление не подтверждает.")
       .setAutoCancel(true)
       .setContentIntent(tap)
       .build();
    manager.notify(100100,notice);
    return true;
  }

  private void issueNotification(String id,String kind,Match match,String start,String rawTitle) {
    NotificationManager manager=(NotificationManager)getSystemService(NOTIFICATION_SERVICE);
    if(manager==null)return;
    if(Build.VERSION.SDK_INT>=26){
      NotificationChannel channel=new NotificationChannel(CHANNEL,"Вода — коммунальные предупреждения",NotificationManager.IMPORTANCE_DEFAULT);
      channel.setDescription("Плановые отключения и аварии, затрагивающие выбранную улицу или дом");
      manager.createNotificationChannel(channel);
    }
    Intent intent=new Intent(this,MainActivity.class);
    PendingIntent tap=PendingIntent.getActivity(this,id.hashCode(),intent,
      PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
    String title=kind.equals("planned")?"Запланированы работы с водой":"Сообщение об ограничении воды";
    String text=match==Match.EXACT?
       "Ваш дом указан в опубликованном уведомлении. Откройте приложение, чтобы проверить время и источник.":
       "Указана ваша улица. Номер дома не подтверждён: уточните подробности в объявлении.";
    Notification n=new Notification.Builder(this,CHANNEL)
       .setSmallIcon(android.R.drawable.stat_notify_error)
       .setContentTitle(title)
       .setContentText(text)
       .setStyle(new Notification.BigTextStyle().bigText(text))
       .setContentIntent(tap)
       .setAutoCancel(true)
       .setOnlyAlertOnce(true)
       .build();
    manager.notify(id.hashCode(),n);
  }
}
