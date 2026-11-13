package ru.citycontrol.don;

import android.app.Application;
import ru.rustore.sdk.pushclient.RuStorePushClient;
import ru.rustore.sdk.pushclient.common.logger.Logger;

public final class DonApplication extends Application {
  static final class QuietLogger implements Logger {
    @Override public void verbose(String m, Throwable t) {}
    @Override public void debug(String m, Throwable t) {}
    @Override public void info(String m, Throwable t) {}
    @Override public void warn(String m, Throwable t) {}
    @Override public void error(String m, Throwable t) {}
    @Override public Logger createLogger(String tag) { return this; }
    @Override public Logger createLogger(Object tag) { return this; }
  }
  @Override public void onCreate() {
    super.onCreate();
    // No invented console project, automatic registration or permission prompt.
    if (!BuildConfig.RUSTORE_PROJECT_ID.isEmpty()) {
      RuStorePushClient.INSTANCE.init(this,BuildConfig.RUSTORE_PROJECT_ID,new QuietLogger());
      if(PushSettings.enabled(this))PushController.enable(this);
    }
  }
}
