package com.littleorbit.wear;

import android.app.Activity;
import android.content.Intent;
import android.graphics.Bitmap;
import android.os.Bundle;
import android.graphics.drawable.GradientDrawable;
import android.view.View;
import android.widget.ImageView;
import android.widget.TextView;
import java.util.Locale;

/** Wear OS launcher surface backed by the last phone-synchronized compact cache. */
public final class WearActivity extends Activity {
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_wear);
        findViewById(R.id.wearCountdown).setOnClickListener(
                view -> startActivity(new Intent(this, WearCountdownActivity.class)));
        findViewById(R.id.wearSmooch).setOnClickListener(
                view -> startActivity(new Intent(this, WearSmoochActivity.class)));
        render();
    }

    @Override
    protected void onResume() {
        super.onResume();
        render();
    }

    private void render() {
        WearDisplayCache.State cache = WearDisplayCache.read(this);
        WearDisplayText display = new WearDisplayText(this);
        TextView together = findViewById(R.id.wearTogether);
        TextView nearby = findViewById(R.id.wearNearby);
        TextView status = findViewById(R.id.wearStatus);
        together.setText(display.nearby(cache));
        nearby.setText(R.string.nearby_estimate_label);
        status.setText(display.status(cache));
        WearConfiguration.State config = WearConfiguration.read(this);
        findViewById(R.id.wearSmooch).setEnabled(config.smoochEnabled());
        nearby.setVisibility(cache.available() ? View.VISIBLE : View.GONE);
        findViewById(R.id.wearEyebrow).setVisibility(cache.available() ? View.VISIBLE : View.GONE);
        findViewById(R.id.wearPlanetRow).setVisibility(cache.available() ? View.VISIBLE : View.GONE);
        if (cache.available()) renderProfiles(config.showPhotos());
        else findViewById(R.id.wearPlanetRow).setVisibility(View.GONE);
    }

    private void renderProfiles(boolean showPhotos) {
        WearProfileStore.State profile = WearProfileStore.read(this);
        findViewById(R.id.wearPlanetRow).setVisibility(View.VISIBLE);
        findViewById(R.id.wearPlanetRow).setContentDescription(getString(
                R.string.orbit_members, displayName(profile.myName()),
                displayName(profile.partnerName())));
        renderPlanet(R.id.wearMyPhoto, R.id.wearMyInitial, profile.myName(),
                showPhotos ? profile.myPhoto() : null);
        renderPlanet(
                R.id.wearPartnerPhoto, R.id.wearPartnerInitial,
                profile.partnerName(), showPhotos ? profile.partnerPhoto() : null);
    }

    private void renderPlanet(int imageId, int fallbackId, String name, Bitmap photo) {
        ImageView image = findViewById(imageId);
        TextView fallback = findViewById(fallbackId);
        if (photo == null) {
            image.setVisibility(android.view.View.GONE);
            fallback.setVisibility(android.view.View.VISIBLE);
            fallback.setText(initial(name));
            return;
        }
        GradientDrawable circle = new GradientDrawable();
        circle.setShape(GradientDrawable.OVAL);
        circle.setColor(android.graphics.Color.TRANSPARENT);
        image.setBackground(circle);
        image.setClipToOutline(true);
        image.setImageBitmap(photo);
        image.setVisibility(android.view.View.VISIBLE);
        fallback.setVisibility(android.view.View.GONE);
    }

    private String initial(String name) {
        if (name == null || name.isBlank()) return getString(R.string.unknown_initial);
        return new String(Character.toChars(name.codePointAt(0))).toUpperCase(Locale.getDefault());
    }

    private String displayName(String name) {
        return name == null || name.isBlank() ? getString(R.string.unavailable) : name;
    }
}
