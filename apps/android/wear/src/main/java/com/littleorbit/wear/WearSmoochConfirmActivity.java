package com.littleorbit.wear;

import android.app.Activity;
import android.os.Bundle;
import android.widget.TextView;
import com.littleorbit.domain.WatchProtocol;
import java.util.UUID;

/** Final confirmation and encrypted offline ownership transfer for one watch Smooch. */
public final class WearSmoochConfirmActivity extends Activity {
    static final String EXTRA_EMOJI = "emoji";
    private static final String STATE_OPERATION_ID = "operation_id";
    private String emoji;
    private String operationId;

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        setContentView(R.layout.activity_wear_smooch_confirm);
        emoji = getIntent().getStringExtra(EXTRA_EMOJI);
        if (!WatchProtocol.approvedEmoji(emoji)) {
            finish();
            return;
        }
        operationId = state == null
                ? UUID.randomUUID().toString()
                : state.getString(STATE_OPERATION_ID, UUID.randomUUID().toString());
        ((TextView) findViewById(R.id.confirmEmoji)).setText(emoji);
        String partner = WearProfileStore.read(this).partnerName();
        ((TextView) findViewById(R.id.confirmPrompt)).setText(getString(
                R.string.send_smooch_to, partner == null || partner.isBlank()
                        ? getString(R.string.your_partner) : partner));
        findViewById(R.id.cancelSmooch).setOnClickListener(view -> finish());
        findViewById(R.id.confirmSmooch).setOnClickListener(view -> send());
    }

    @Override
    protected void onSaveInstanceState(Bundle state) {
        state.putString(STATE_OPERATION_ID, operationId);
        super.onSaveInstanceState(state);
    }

    private void send() {
        findViewById(R.id.confirmSmooch).setEnabled(false);
        WearRelationshipPolicy.State relationship = WearRelationshipGuard.current(this);
        if (!WearConfiguration.read(this).smoochEnabled()
                || !WearRelationshipPolicy.readable(relationship)) {
            ((TextView) findViewById(R.id.confirmStatus)).setText(R.string.smooch_unavailable);
            findViewById(R.id.confirmSmooch).setEnabled(true);
            return;
        }
        long now = System.currentTimeMillis();
        WearSmoochQueue.enqueue(this, operationId, emoji, now,
                relationship.relationshipId(), relationship.generation(),
                WearTargetGuard.generation(this));
        WearActionService.flush(this);
        ((TextView) findViewById(R.id.confirmStatus)).setText(R.string.smooch_queued);
    }
}
