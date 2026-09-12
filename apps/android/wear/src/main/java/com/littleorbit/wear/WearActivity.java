package com.littleorbit.wear;

import android.app.Activity;
import android.os.Bundle;

/** Wear OS launcher surface backed by the last phone-synchronized compact cache. */
public final class WearActivity extends Activity {
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_wear);
        render();
    }

    @Override
    protected void onResume() {
        super.onResume();
        render();
    }

    private void render() {
        WearDisplayCache.State cache = WearDisplayCache.read(this);
        findViewById(android.R.id.content).setContentDescription(cache.accessibilityText());
        ((android.widget.TextView) findViewById(R.id.wearTogether))
                .setText(cache.relationshipText());
        ((android.widget.TextView) findViewById(R.id.wearNearby))
                .setText(cache.nearbyText());
        ((android.widget.TextView) findViewById(R.id.wearStatus))
                .setText(cache.statusText());
    }
}
