package com.littleorbit.wear;

import android.app.Activity;
import android.os.Bundle;
import android.graphics.drawable.GradientDrawable;
import android.widget.ImageView;
import android.widget.TextView;

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
        renderProfiles();
    }

    private void renderProfiles() {
        WearProfileStore.State profile = WearProfileStore.read(this);
        renderPlanet(R.id.wearMyPhoto, R.id.wearMyInitial, profile.myName(), profile.myPhoto());
        renderPlanet(
                R.id.wearPartnerPhoto, R.id.wearPartnerInitial,
                profile.partnerName(), profile.partnerPhoto());
    }

    private void renderPlanet(int imageId, int fallbackId, String name, android.graphics.Bitmap photo) {
        ImageView image = findViewById(imageId);
        TextView fallback = findViewById(fallbackId);
        if (photo == null) {
            image.setVisibility(android.view.View.GONE);
            fallback.setVisibility(android.view.View.VISIBLE);
            fallback.setText(name == null || name.isBlank() ? "?" : name.substring(0, 1).toUpperCase());
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
}
