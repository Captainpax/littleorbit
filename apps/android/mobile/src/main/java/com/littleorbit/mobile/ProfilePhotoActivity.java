package com.littleorbit.mobile;

import android.app.Activity;
import android.content.Intent;
import android.graphics.BitmapFactory;
import android.net.Uri;
import android.os.Bundle;
import android.view.View;
import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.contract.ActivityResultContracts;
import com.littleorbit.data.repository.ProfileRepository;
import com.littleorbit.mobile.databinding.ActivityProfilePhotoBinding;
import dagger.hilt.android.AndroidEntryPoint;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import javax.inject.Inject;

/** Relationship-avatar picker where each person chooses only their partner's image. */
@AndroidEntryPoint
public final class ProfilePhotoActivity extends OrbitShellActivity {
    private static final int MAX_UPLOAD_BYTES = 5 * 1024 * 1024;
    private ActivityProfilePhotoBinding binding;
    @Inject ProfileRepository profiles;

    private final ActivityResultLauncher<String> pickPhoto = registerForActivityResult(
            new ActivityResultContracts.GetContent(), uri -> {
                if (uri != null) openCrop(uri);
            });
    private final ActivityResultLauncher<Intent> cropPhoto = registerForActivityResult(
            new ActivityResultContracts.StartActivityForResult(), result -> {
                Intent data = result.getData();
                if (result.getResultCode() == Activity.RESULT_OK && data != null) {
                    handleCrop(data.getData());
                }
            });

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        binding = ActivityProfilePhotoBinding.inflate(getLayoutInflater());
        setContentView(binding.getRoot());
        binding.choosePhoto.setOnClickListener(view -> pickPhoto.launch("image/*"));
        binding.removePhoto.setOnClickListener(view -> removePhoto());
        render(profiles.cached());
        profiles.refresh().thenAccept(state -> runOnUiThread(() -> render(state)));
    }

    @Override
    protected OrbitDestination orbitDestination() {
        return OrbitDestination.PROFILE;
    }

    private void openCrop(Uri source) {
        cropPhoto.launch(ProfileCropActivity.intent(this, source));
    }

    private void handleCrop(Uri resultUri) {
        if (resultUri == null) {
            binding.profileStatus.setText(R.string.photo_crop_failed);
            return;
        }
        try {
            upload(readBounded(resultUri));
        } catch (IOException | RuntimeException failure) {
            binding.profileStatus.setText(R.string.photo_crop_failed);
        } finally {
            getContentResolver().delete(resultUri, null, null);
        }
    }

    private byte[] readBounded(Uri uri) throws IOException {
        try (InputStream input = getContentResolver().openInputStream(uri);
                ByteArrayOutputStream output = new ByteArrayOutputStream()) {
            if (input == null) throw new IOException("Crop output is unavailable");
            byte[] buffer = new byte[8192];
            int total = 0;
            int count;
            while ((count = input.read(buffer)) != -1) {
                total += count;
                if (total > MAX_UPLOAD_BYTES) throw new IOException("Crop is too large");
                output.write(buffer, 0, count);
            }
            return output.toByteArray();
        }
    }

    private void upload(byte[] webp) {
        setBusy(true);
        profiles.uploadPartnerPhoto(webp).thenAccept(state -> runOnUiThread(() -> {
            render(state);
            binding.profileStatus.setText(R.string.partner_avatar_saved);
            setBusy(false);
        })).exceptionally(failure -> {
            runOnUiThread(this::fail);
            return null;
        });
    }

    private void removePhoto() {
        setBusy(true);
        profiles.deletePartnerPhoto().thenAccept(state -> runOnUiThread(() -> {
            render(state);
            binding.profileStatus.setText(R.string.partner_avatar_removed);
            setBusy(false);
        })).exceptionally(failure -> {
            runOnUiThread(this::fail);
            return null;
        });
    }

    private void render(ProfileRepository.State state) {
        renderOwn(state);
        String partnerName = state.paired() ? state.partnerName() : getString(R.string.not_paired);
        binding.profileName.setText(partnerName);
        binding.profileInitial.setText(initial(partnerName));
        byte[] bytes = state.partnerPhoto();
        if (bytes == null) {
            binding.profilePreview.setVisibility(View.GONE);
            binding.profileInitial.setVisibility(View.VISIBLE);
            binding.removePhoto.setEnabled(false);
            binding.choosePhoto.setEnabled(state.paired());
            return;
        }
        binding.profilePreview.setImageBitmap(BitmapFactory.decodeByteArray(bytes, 0, bytes.length));
        binding.profilePreview.setVisibility(View.VISIBLE);
        binding.profileInitial.setVisibility(View.GONE);
        binding.removePhoto.setEnabled(true);
        binding.choosePhoto.setEnabled(true);
    }

    private void renderOwn(ProfileRepository.State state) {
        binding.myName.setText(state.myName());
        binding.myInitial.setText(initial(state.myName()));
        byte[] bytes = state.myPhoto();
        binding.myPreview.setVisibility(bytes == null ? View.GONE : View.VISIBLE);
        binding.myInitial.setVisibility(bytes == null ? View.VISIBLE : View.GONE);
        if (bytes != null) {
            binding.myPreview.setImageBitmap(BitmapFactory.decodeByteArray(bytes, 0, bytes.length));
        }
    }

    private void setBusy(boolean busy) {
        binding.profileProgress.setVisibility(busy ? View.VISIBLE : View.GONE);
        ProfileRepository.State state = profiles.cached();
        binding.choosePhoto.setEnabled(!busy && state.paired());
        binding.removePhoto.setEnabled(!busy && state.paired() && state.partnerPhoto() != null);
    }

    private void fail() {
        setBusy(false);
        binding.profileStatus.setText(R.string.request_failed);
    }

    private static String initial(String name) {
        return name == null || name.isBlank() ? "Y" : name.substring(0, 1).toUpperCase();
    }
}
