package com.littleorbit.mobile;

import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.net.Uri;
import android.os.Bundle;
import android.view.View;
import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.contract.ActivityResultContracts;
import com.canhub.cropper.CropImageContract;
import com.canhub.cropper.CropImageContractOptions;
import com.canhub.cropper.CropImageOptions;
import com.canhub.cropper.CropImageView;
import com.littleorbit.data.repository.ProfileRepository;
import com.littleorbit.mobile.databinding.ActivityProfilePhotoBinding;
import dagger.hilt.android.AndroidEntryPoint;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import javax.inject.Inject;

/** Private profile-photo picker with explicit square crop and server replacement. */
@AndroidEntryPoint
public final class ProfilePhotoActivity extends InsetAwareActivity {
    private static final int MAX_UPLOAD_BYTES = 5 * 1024 * 1024;
    private ActivityProfilePhotoBinding binding;
    @Inject ProfileRepository profiles;

    private final ActivityResultLauncher<String> pickPhoto = registerForActivityResult(
            new ActivityResultContracts.GetContent(), uri -> { if (uri != null) crop(uri); });
    private final ActivityResultLauncher<CropImageContractOptions> cropPhoto =
            registerForActivityResult(new CropImageContract(), this::handleCrop);

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

    private void crop(Uri source) {
        CropImageOptions options = new CropImageOptions();
        options.fixAspectRatio = true;
        options.aspectRatioX = 1;
        options.aspectRatioY = 1;
        options.cropShape = CropImageView.CropShape.OVAL;
        options.outputCompressFormat = Bitmap.CompressFormat.WEBP;
        options.outputCompressQuality = 88;
        options.outputRequestWidth = 512;
        options.outputRequestHeight = 512;
        options.activityTitle = getString(R.string.crop_profile_photo);
        cropPhoto.launch(new CropImageContractOptions(source, options));
    }

    private void handleCrop(CropImageView.CropResult result) {
        if (!result.isSuccessful()) {
            if (result.getError() != null) binding.profileStatus.setText(R.string.photo_crop_failed);
            return;
        }
        try {
            Bitmap bitmap = result.getBitmap(this);
            if (bitmap == null) throw new IOException("Crop output is unavailable");
            ByteArrayOutputStream output = new ByteArrayOutputStream();
            if (!bitmap.compress(Bitmap.CompressFormat.WEBP, 88, output)) {
                throw new IOException("Could not encode crop");
            }
            byte[] webp = output.toByteArray();
            if (webp.length > MAX_UPLOAD_BYTES) throw new IOException("Crop is too large");
            upload(webp);
        } catch (IOException | RuntimeException failure) {
            binding.profileStatus.setText(R.string.photo_crop_failed);
        }
    }

    private void upload(byte[] webp) {
        setBusy(true);
        profiles.upload(webp).thenAccept(state -> runOnUiThread(() -> {
            render(state);
            binding.profileStatus.setText(R.string.profile_photo_saved);
            setBusy(false);
        })).exceptionally(failure -> { runOnUiThread(() -> fail()); return null; });
    }

    private void removePhoto() {
        setBusy(true);
        profiles.deleteOwnPhoto().thenAccept(state -> runOnUiThread(() -> {
            render(state);
            binding.profileStatus.setText(R.string.profile_photo_removed);
            setBusy(false);
        })).exceptionally(failure -> { runOnUiThread(() -> fail()); return null; });
    }

    private void render(ProfileRepository.State state) {
        binding.profileName.setText(state.myName());
        binding.profileInitial.setText(initial(state.myName()));
        byte[] bytes = state.myPhoto();
        if (bytes == null) {
            binding.profilePreview.setVisibility(View.GONE);
            binding.profileInitial.setVisibility(View.VISIBLE);
            binding.removePhoto.setEnabled(false);
            return;
        }
        binding.profilePreview.setImageBitmap(BitmapFactory.decodeByteArray(bytes, 0, bytes.length));
        binding.profilePreview.setVisibility(View.VISIBLE);
        binding.profileInitial.setVisibility(View.GONE);
        binding.removePhoto.setEnabled(true);
    }

    private void setBusy(boolean busy) {
        binding.profileProgress.setVisibility(busy ? View.VISIBLE : View.GONE);
        binding.choosePhoto.setEnabled(!busy);
        binding.removePhoto.setEnabled(!busy && profiles.cached().myPhoto() != null);
    }

    private void fail() { setBusy(false); binding.profileStatus.setText(R.string.request_failed); }

    private static String initial(String name) {
        return name == null || name.isBlank() ? "Y" : name.substring(0, 1).toUpperCase();
    }
}
