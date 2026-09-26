package com.littleorbit.mobile;

import android.app.Activity;
import android.content.Intent;
import android.graphics.BitmapFactory;
import android.net.Uri;
import android.os.Bundle;
import android.view.View;
import android.view.inputmethod.EditorInfo;
import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.contract.ActivityResultContracts;
import com.google.android.material.dialog.MaterialAlertDialogBuilder;
import com.littleorbit.data.repository.OrbitServiceException;
import com.littleorbit.data.repository.PartnerNameRules;
import com.littleorbit.data.repository.ProfileRepository;
import com.littleorbit.mobile.databinding.ActivityProfilePhotoBinding;
import dagger.hilt.android.AndroidEntryPoint;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.util.Locale;
import java.util.concurrent.CompletionException;
import javax.inject.Inject;

/** Partner-controlled relationship names and avatars with explicit shared ownership. */
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
        binding.removePhoto.setOnClickListener(view -> askToRemovePhoto());
        binding.savePartnerName.setOnClickListener(view -> savePartnerName());
        binding.resetPartnerName.setOnClickListener(view -> resetPartnerName());
        binding.partnerNameInput.setOnEditorActionListener((view, action, event) -> {
            if (action != EditorInfo.IME_ACTION_DONE) return false;
            savePartnerName();
            return true;
        });
        render(profiles.cached());
        profiles.refresh().thenAccept(state -> runOnUiThread(() -> {
            if (!isFinishing() && !isDestroyed()) render(state);
        }));
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
            if (isFinishing() || isDestroyed()) return;
            render(state);
            binding.profileStatus.setText(R.string.partner_avatar_saved);
            setBusy(false);
        })).exceptionally(failure -> {
            runOnUiThread(() -> {
                if (!isFinishing() && !isDestroyed()) fail();
            });
            return null;
        });
    }

    private void removePhoto() {
        setBusy(true);
        profiles.deletePartnerPhoto().thenAccept(state -> runOnUiThread(() -> {
            if (isFinishing() || isDestroyed()) return;
            render(state);
            binding.profileStatus.setText(R.string.partner_avatar_removed);
            setBusy(false);
        })).exceptionally(failure -> {
            runOnUiThread(() -> {
                if (!isFinishing() && !isDestroyed()) fail();
            });
            return null;
        });
    }

    private void askToRemovePhoto() {
        ProfileRepository.State state = profiles.cached();
        if (!state.paired() || state.partnerPhoto() == null) return;
        String partnerName = state.partnerName();
        new MaterialAlertDialogBuilder(this)
                .setTitle(getString(R.string.rc14_remove_partner_avatar_title, partnerName))
                .setMessage(R.string.rc14_remove_partner_avatar_message)
                .setNegativeButton(R.string.cancel, null)
                .setPositiveButton(
                        getString(R.string.rc14_remove_partner_avatar, partnerName),
                        (dialog, which) -> removePhoto())
                .show();
    }

    private void savePartnerName() {
        String entered = String.valueOf(binding.partnerNameInput.getText());
        final String normalized;
        try {
            normalized = PartnerNameRules.normalize(entered);
        } catch (IllegalArgumentException invalid) {
            binding.partnerNameLayout.setError(getString(R.string.partner_name_invalid));
            return;
        }
        binding.partnerNameLayout.setError(null);
        setBusy(true);
        profiles.savePartnerName(normalized).thenAccept(state -> runOnUiThread(() -> {
            if (isFinishing() || isDestroyed()) return;
            binding.partnerNameInput.setText(normalized);
            render(state);
            binding.profileStatus.setText(R.string.partner_name_saved);
            setBusy(false);
        })).exceptionally(failure -> {
            runOnUiThread(() -> handleNameFailure(failure));
            return null;
        });
    }

    private void resetPartnerName() {
        setBusy(true);
        profiles.resetPartnerName().thenAccept(state -> runOnUiThread(() -> {
            if (isFinishing() || isDestroyed()) return;
            binding.partnerNameInput.setText("");
            render(state);
            binding.profileStatus.setText(R.string.partner_name_reset_done);
            setBusy(false);
        })).exceptionally(failure -> {
            runOnUiThread(() -> handleNameFailure(failure));
            return null;
        });
    }

    private void handleNameFailure(Throwable failure) {
        if (isFinishing() || isDestroyed()) return;
        setBusy(false);
        Throwable cause = failure instanceof CompletionException && failure.getCause() != null
                ? failure.getCause() : failure;
        if (cause instanceof OrbitServiceException service && service.statusCode() == 409) {
            binding.profileStatus.setText(R.string.partner_name_conflict);
            profiles.refresh().thenAccept(state -> runOnUiThread(() -> {
                if (!isFinishing() && !isDestroyed()) render(state);
            }));
            return;
        }
        binding.profileStatus.setText(R.string.request_failed);
    }

    private void render(ProfileRepository.State state) {
        renderOwn(state);
        String partnerName = state.paired() ? state.partnerName() : getString(R.string.not_paired);
        binding.profileName.setText(partnerName);
        binding.profileInitial.setText(initial(partnerName));
        binding.partnerAvatarLabel.setText(getString(
                R.string.rc14_partner_avatar_heading, partnerName));
        binding.removePhoto.setText(getString(
                R.string.rc14_remove_partner_avatar, partnerName));
        String partnerDescription = getString(
                R.string.rc14_partner_avatar_description, partnerName);
        binding.profilePreview.setContentDescription(partnerDescription);
        binding.profileInitial.setContentDescription(partnerDescription);
        binding.partnerNameInput.setContentDescription(getString(
                R.string.partner_name_input_description, partnerName));
        if (!binding.partnerNameInput.hasFocus()) {
            binding.partnerNameInput.setText(
                    state.partnerNameAssigned() ? state.partnerName() : "");
        }
        binding.resetPartnerName.setEnabled(state.paired() && state.partnerNameAssigned());
        byte[] bytes = state.partnerPhoto();
        if (bytes == null) {
            binding.profilePreview.setVisibility(View.GONE);
            binding.profileInitial.setVisibility(View.VISIBLE);
            binding.removePhoto.setEnabled(false);
            binding.choosePhoto.setEnabled(state.paired());
            binding.choosePhoto.setText(getString(
                    R.string.rc14_choose_partner_avatar, partnerName));
            return;
        }
        binding.profilePreview.setImageBitmap(BitmapFactory.decodeByteArray(bytes, 0, bytes.length));
        binding.profilePreview.setVisibility(View.VISIBLE);
        binding.profileInitial.setVisibility(View.GONE);
        binding.removePhoto.setEnabled(true);
        binding.choosePhoto.setEnabled(true);
        binding.choosePhoto.setText(getString(
                R.string.rc14_replace_partner_avatar, partnerName));
    }

    private void renderOwn(ProfileRepository.State state) {
        binding.myName.setText(state.myName());
        binding.myInitial.setText(initial(state.myName()));
        binding.myPreview.setContentDescription(getString(R.string.rc14_own_avatar_description));
        binding.myInitial.setContentDescription(getString(R.string.rc14_own_avatar_description));
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
        binding.partnerNameInput.setEnabled(!busy && state.paired());
        binding.savePartnerName.setEnabled(!busy && state.paired());
        binding.resetPartnerName.setEnabled(
                !busy && state.paired() && state.partnerNameAssigned());
    }

    private void fail() {
        setBusy(false);
        binding.profileStatus.setText(R.string.request_failed);
    }

    private static String initial(String name) {
        return name == null || name.isBlank()
                ? "Y" : name.substring(0, name.offsetByCodePoints(0, 1)).toUpperCase(Locale.ROOT);
    }
}
