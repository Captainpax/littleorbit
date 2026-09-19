package com.littleorbit.wear;

import android.app.Activity;
import android.content.Intent;
import android.os.Bundle;

/** Opens the phone-selected watch destination without creating a horizontal pager. */
public final class WearRouterActivity extends Activity {
    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        WearConfiguration.State config = WearConfiguration.read(this);
        Class<? extends Activity> destination = WearActivity.class;
        if ("countdown".equals(config.defaultDestination())) {
            destination = WearCountdownActivity.class;
        } else if ("smooch".equals(config.defaultDestination()) && config.smoochEnabled()) {
            destination = WearSmoochActivity.class;
        }
        startActivity(new Intent(this, destination));
        finish();
    }
}
