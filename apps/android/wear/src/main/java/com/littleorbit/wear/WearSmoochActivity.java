package com.littleorbit.wear;

import android.app.Activity;
import android.content.Intent;
import android.os.Bundle;
import android.view.View;
import android.widget.Button;
import com.littleorbit.domain.WatchProtocol;

/** Approved emoji picker; sending always requires the separate confirmation screen. */
public final class WearSmoochActivity extends Activity {
    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        setContentView(R.layout.activity_wear_smooch);
        int[] ids = {R.id.smooch0, R.id.smooch1, R.id.smooch2, R.id.smooch3, R.id.smooch4,
                R.id.smooch5, R.id.smooch6, R.id.smooch7, R.id.smooch8};
        for (int index = 0; index < ids.length; index++) {
            String emoji = WatchProtocol.SMOOCH_EMOJIS.get(index);
            Button button = findViewById(ids[index]);
            button.setText(emoji);
            button.setOnClickListener(view -> confirm(emoji));
        }
        findViewById(R.id.smoochTogether).setOnClickListener(
                view -> startActivity(new Intent(this, WearActivity.class)));
        findViewById(R.id.smoochCountdown).setOnClickListener(
                view -> startActivity(new Intent(this, WearCountdownActivity.class)));
    }

    @Override
    protected void onResume() {
        super.onResume();
        boolean enabled = WearConfiguration.read(this).smoochEnabled()
                && WearRelationshipPolicy.readable(WearRelationshipGuard.current(this));
        findViewById(R.id.smoochGrid).setVisibility(enabled ? View.VISIBLE : View.GONE);
        findViewById(R.id.smoochUnavailable).setVisibility(enabled ? View.GONE : View.VISIBLE);
    }

    private void confirm(String emoji) {
        startActivity(new Intent(this, WearSmoochConfirmActivity.class)
                .putExtra(WearSmoochConfirmActivity.EXTRA_EMOJI, emoji));
    }
}
