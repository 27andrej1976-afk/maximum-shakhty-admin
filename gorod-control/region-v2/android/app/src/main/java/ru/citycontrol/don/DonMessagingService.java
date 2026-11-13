package ru.citycontrol.don;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Intent;
import android.os.SystemClock;
import java.net.HttpURLConnection;
import java.net.URL;
import java.io.ByteArrayOutputStream;
import java.util.List;
import java.util.Map;
import org.json.JSONObject;
import ru.rustore.sdk.pushclient.messaging.service.RuStoreMessagingService;
import ru.rustore.sdk.pushclient.messaging.model.RemoteMessage;
import ru.rustore.sdk.pushclient.messaging.exception.RuStorePushClientException;

public final class DonMessagingService extends RuStoreMessagingService {
  private static final String CHANNEL="don-nearby-v1";
  @Override public void onNewToken(String token){if(PushSettings.enabled(this))PushController.enable(this);}
  @Override public void onDeletedMessages(){PushController.note(this,"Часть уведомлений не доставлена. Откройте приложение и нажмите «Проверить сообщения».");}
  @Override public void onError(List<? extends RuStorePushClientException> errors){PushController.note(this,"Сервис RuStore сообщил об ошибке доставки. Проверьте доступность уведомлений.");}
  @android.annotation.SuppressLint("MissingPermission") // PushController.allowed is rechecked under the same lock before notify.
  @Override public void onMessageReceived(RemoteMessage message){
    // Backend is required to send DATA ONLY. Never trust pushed coordinates/text/URLs.
    if(!PushSettings.enabled(this)||!PushSettings.hasPoint(this)||!PushController.allowed(this)||BuildConfig.RUSTORE_PROJECT_ID.isEmpty())return;
    Map<String,String> data=message.getData();String id=data.get("eventId"),hash=data.get("sourceHash");
    if(!"don-event-v1".equals(data.get("type"))||id==null||id.length()>180||hash==null||!hash.matches("[a-f0-9]{64}"))return;
    try{
      long sent=java.time.Instant.parse(data.get("sentAt")).toEpochMilli(),now=System.currentTimeMillis();
      if(now-sent>300000||sent>now+60000)return;
      String dedupe="seen:"+id+":"+hash;
      if(PushSettings.prefs(this).contains(dedupe))return;
      JSONObject feed=fetch();now=System.currentTimeMillis();
      JSONObject event=PushPolicy.find(feed,id,hash,PushSettings.lat(this),PushSettings.lon(this),PushSettings.prefs(this).getInt("radius",1),now);
      // Re-check consent after network fetch: deletion/disable can happen meanwhile.
      if(event==null||!PushSettings.enabled(this)||!PushSettings.hasPoint(this)||!PushController.allowed(this))return;
      NotificationManager manager=getSystemService(NotificationManager.class);
      manager.createNotificationChannel(new NotificationChannel(CHANNEL,"События рядом и предупреждения МЧС",NotificationManager.IMPORTANCE_DEFAULT));
      Intent open=new Intent(this,MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP|Intent.FLAG_ACTIVITY_SINGLE_TOP);
      PendingIntent click=PendingIntent.getActivity(this,0,open,PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE);
      String body="region".equals(event.optString("scope"))?"Предупреждение для Ростовской области. Откройте публикацию источника.":"Уличный ориентир в выбранном радиусе. Точные границы — в публикации источника.";
      Notification notice=new Notification.Builder(this,CHANNEL).setSmallIcon(R.drawable.ic_notification).setContentTitle(event.getString("title")).setContentText(body).setStyle(new Notification.BigTextStyle().bigText(body)).setContentIntent(click).setAutoCancel(true).build();
      synchronized(PushSettings.class){
        if(!PushSettings.enabled(this)||!PushSettings.hasPoint(this)||!PushController.allowed(this)||PushSettings.prefs(this).contains(dedupe))return;
        if(PushPolicy.find(feed,id,hash,PushSettings.lat(this),PushSettings.lon(this),PushSettings.prefs(this).getInt("radius",1),System.currentTimeMillis())==null)return;
        manager.notify(id,1,notice);PushSettings.prefs(this).edit().putLong(dedupe,now).apply();
      }
      // Bounded local delivery history, no device IDs or GPS leave the phone.
      android.content.SharedPreferences.Editor edit=PushSettings.prefs(this).edit();
      for(Map.Entry<String,?> entry:PushSettings.prefs(this).getAll().entrySet())if(entry.getKey().startsWith("seen:")&&entry.getValue() instanceof Long&&(Long)entry.getValue()<now-7*86400000L)edit.remove(entry.getKey());
      edit.apply();
    }catch(Exception error){PushController.note(this,"Не удалось подтвердить событие для уведомления. Смотрите свежую сводку в приложении.");}
  }
  private JSONObject fetch() throws Exception {
    HttpURLConnection connection=(HttpURLConnection)new URL("https://chat.sportoskop.ru/don-control/feed.json").openConnection();
    connection.setConnectTimeout(3000);connection.setReadTimeout(3000);connection.setInstanceFollowRedirects(false);connection.setUseCaches(false);
    long deadline=SystemClock.elapsedRealtime()+8000;
    try{
      if(connection.getResponseCode()!=200)throw new java.io.IOException("Feed unavailable");
      try(java.io.InputStream input=connection.getInputStream();ByteArrayOutputStream output=new ByteArrayOutputStream()){
        byte[] buffer=new byte[16384];int count;
        while((count=input.read(buffer))!=-1){if(output.size()+count>8*1024*1024||SystemClock.elapsedRealtime()>deadline)throw new java.io.IOException("Feed bound");output.write(buffer,0,count);}
        return new JSONObject(output.toString("UTF-8"));
      }
    }finally{connection.disconnect();}
  }
}
