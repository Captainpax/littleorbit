package com.littleorbit.mobile;

import android.content.Context;
import android.util.AttributeSet;
import android.view.LayoutInflater;
import android.view.View;
import android.widget.LinearLayout;
import android.widget.TextView;
import androidx.annotation.Nullable;
import com.google.android.material.button.MaterialButton;

/** Resumable Home checklist surface with explicit actions for each optional capability. */
public final class SetupChecklistView extends LinearLayout {
    /** Host callbacks keep navigation and permissions outside this presentation view. */
    public interface Listener {
        void onPairing();
        void onNotifications();
        void onNearbyTime();
        void onWidget();
        void onWatch();
        void onCollapsedChanged(boolean collapsed);
    }

    private final TextView summary;
    private final TextView pairingStatus;
    private final TextView notificationStatus;
    private final TextView nearbyStatus;
    private final TextView widgetStatus;
    private final TextView watchStatus;
    private final LinearLayout details;
    private final MaterialButton toggle;
    private final MaterialButton pairingAction;
    private final MaterialButton notificationAction;
    private final MaterialButton nearbyAction;
    private final MaterialButton widgetAction;
    private final MaterialButton watchAction;

    public SetupChecklistView(Context context) {
        this(context, null);
    }

    public SetupChecklistView(Context context, @Nullable AttributeSet attributes) {
        super(context, attributes);
        setOrientation(VERTICAL);
        LayoutInflater.from(context).inflate(R.layout.view_setup_checklist, this, true);
        summary = findViewById(R.id.setupChecklistSummary);
        pairingStatus = findViewById(R.id.setupPairingStatus);
        notificationStatus = findViewById(R.id.setupNotificationStatus);
        nearbyStatus = findViewById(R.id.setupNearbyStatus);
        widgetStatus = findViewById(R.id.setupWidgetStatus);
        watchStatus = findViewById(R.id.setupWatchStatus);
        details = findViewById(R.id.setupChecklistDetails);
        toggle = findViewById(R.id.setupChecklistToggle);
        pairingAction = findViewById(R.id.setupPairingAction);
        notificationAction = findViewById(R.id.setupNotificationAction);
        nearbyAction = findViewById(R.id.setupNearbyAction);
        widgetAction = findViewById(R.id.setupWidgetAction);
        watchAction = findViewById(R.id.setupWatchAction);
    }

    /** Renders one immutable snapshot and replaces every action listener. */
    public void bind(SetupChecklistState state, Listener listener) {
        summary.setText(getResources().getQuantityString(
                R.plurals.rc14_setup_ready_count, state.readyCount(), state.readyCount()));
        status(pairingStatus, state.pairingReady(), R.string.rc14_setup_pairing_needed);
        status(notificationStatus, state.notificationsReady(), R.string.rc14_setup_off_optional);
        status(nearbyStatus, state.nearbyReady(), R.string.rc14_setup_off_optional);
        status(widgetStatus, state.widgetReady(), R.string.rc14_setup_widget_missing);
        status(watchStatus, state.watchReady(), R.string.rc14_setup_watch_optional);
        details.setVisibility(state.collapsed() ? View.GONE : View.VISIBLE);
        toggle.setText(state.collapsed()
                ? R.string.rc14_setup_expand : R.string.rc14_setup_collapse);
        toggle.setOnClickListener(ignored -> listener.onCollapsedChanged(!state.collapsed()));
        pairingAction.setOnClickListener(ignored -> listener.onPairing());
        notificationAction.setOnClickListener(ignored -> listener.onNotifications());
        nearbyAction.setOnClickListener(ignored -> listener.onNearbyTime());
        widgetAction.setOnClickListener(ignored -> listener.onWidget());
        watchAction.setOnClickListener(ignored -> listener.onWatch());
    }

    private void status(TextView view, boolean ready, int unavailableText) {
        view.setText(ready ? R.string.rc14_setup_ready : unavailableText);
        view.setTextColor(getContext().getColor(
                ready ? R.color.mint : R.color.muted));
    }
}
