package com.littleorbit.wear;

import android.app.Activity;
import android.content.Intent;
import android.os.Bundle;
import android.widget.TextView;
import java.time.Instant;

/** Vertical countdown destination with exact timed/all-day semantics and stale state. */
public final class WearCountdownActivity extends Activity {
    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        setContentView(R.layout.activity_wear_countdown);
        findViewById(R.id.countdownTogether).setOnClickListener(
                view -> startActivity(new Intent(this, WearActivity.class)));
        findViewById(R.id.countdownSmooch).setOnClickListener(
                view -> startActivity(new Intent(this, WearSmoochActivity.class)));
    }

    @Override
    protected void onResume() {
        super.onResume();
        WearDisplayCache.State cache = WearDisplayCache.read(this);
        ((TextView) findViewById(R.id.countdownTitle)).setText(
                WearCountdownText.title(this, cache));
        ((TextView) findViewById(R.id.countdownRemaining)).setText(
                WearCountdownText.remaining(this, cache, Instant.now()));
        ((TextView) findViewById(R.id.countdownWhen)).setText(
                WearCountdownText.when(this, cache));
        ((TextView) findViewById(R.id.countdownFreshness)).setText(cache.stale()
                ? R.string.stale_open_phone : R.string.synced_from_phone);
        findViewById(R.id.countdownSmooch).setEnabled(
                WearConfiguration.read(this).smoochEnabled());
    }
}
