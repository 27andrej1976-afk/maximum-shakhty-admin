package ru.citycontrol.don;

import android.Manifest;
import android.app.NotificationManager;
import android.content.Context;
import android.content.pm.PackageManager;
import android.os.Build;
import org.json.JSONObject;
import java.util.concurrent.atomic.AtomicInteger;
import ru.rustore.sdk.pushclient.RuStorePushClient;

final class PushController {
  static final String[] TOPICS={"don-water-v1","don-power-v1","don-mchs-v1"};
  private static final AtomicInteger generation=new AtomicInteger();
  static boolean allowed(Context c){return (Build.VERSION.SDK_INT<33||c.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)==PackageManager.PERMISSION_GRANTED)&&c.getSystemService(NotificationManager.class).areNotificationsEnabled();}
  static void note(Context c,String text){PushSettings.prefs(c).edit().putString("status",text).apply();}
  static void disable(Context c){
    if(!PushSettings.enabled(c))return;
    generation.incrementAndGet();PushSettings.prefs(c).edit().putBoolean("enabled",false).apply();
    c.getSystemService(NotificationManager.class).cancelAll();note(c,"Уведомления выключены.");
    if(RuStorePushClient.INSTANCE.isInitialized())for(String topic:TOPICS)RuStorePushClient.INSTANCE.unsubscribeFromTopic(topic);
  }
  static void enable(Context context){
    Context c=context.getApplicationContext();
    if(BuildConfig.RUSTORE_PROJECT_ID.isEmpty()||!RuStorePushClient.INSTANCE.isInitialized()){note(c,"Push-проект RuStore ещё не подключён. Доставка пока недоступна.");return;}
    if(!PushSettings.hasPoint(c)||!allowed(c)){note(c,"Нужны контрольная точка и разрешение на уведомления.");return;}
    int attempt=generation.incrementAndGet();PushSettings.prefs(c).edit().putBoolean("enabled",true).apply();
    note(c,"Проверяем доступность доставки RuStore…");
    RuStorePushClient.INSTANCE.checkPushAvailability().addOnSuccessListener(result->{
      if(attempt!=generation.get()||!PushSettings.enabled(c))return;
      AtomicInteger left=new AtomicInteger(TOPICS.length);
      for(String topic:TOPICS)RuStorePushClient.INSTANCE.subscribeToTopic(topic).addOnSuccessListener(done->{
        if(attempt!=generation.get()||!PushSettings.enabled(c)){RuStorePushClient.INSTANCE.unsubscribeFromTopic(topic);return;}
        if(left.decrementAndGet()==0)note(c,"Подписка RuStore оформлена. События проверяются по радиусу на устройстве; МЧС — по области. Доставка зависит от сети и настроек Android.");
      }).addOnFailureListener(error->{if(attempt==generation.get()){disable(c);note(c,"Не удалось оформить подписку. Нажмите включение для повтора.");}});
    }).addOnFailureListener(error->{if(attempt==generation.get()){disable(c);note(c,"Доставка RuStore недоступна. Проверьте вход в RuStore и разрешение фоновой работы.");}});
  }
  static JSONObject status(Context c){
    JSONObject out=new JSONObject();try{
      boolean enabled=PushSettings.enabled(c)&&allowed(c)&&!BuildConfig.RUSTORE_PROJECT_ID.isEmpty();
      out.put("enabled",enabled);out.put("message",BuildConfig.RUSTORE_PROJECT_ID.isEmpty()?"Push-проект RuStore ещё не подключён. Уведомления пока не доставляются.":PushSettings.prefs(c).getString("status","Уведомления выключены. Точка остаётся на устройстве."));
    }catch(Exception ignored){}return out;
  }
}
