package com.littleorbit.mobile;

import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.graphics.Bitmap;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.util.Log;
import android.view.View;
import androidx.core.content.FileProvider;
import com.canhub.cropper.CropImageView;
import com.littleorbit.mobile.databinding.ActivityProfileCropBinding;
import java.io.File;
import java.io.IOException;

/** Inset-safe first-party photo crop flow with explicit approval and cancellation. */
public final class ProfileCropActivity extends InsetAwareActivity {
    private static final String TAG = "OrbitProfileCrop";
    private static final String OUTPUT_DIRECTORY = "profile-crops";
    private ActivityProfileCropBinding binding;
    private File outputFile;
    private boolean resultDelivered;

    /** Creates an internal crop request while retaining read access to the selected image. */
    public static Intent intent(Context context, Uri source) {
        return new Intent(context, ProfileCropActivity.class)
                .setData(source)
                .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
    }

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        binding = ActivityProfileCropBinding.inflate(getLayoutInflater());
        setContentView(binding.getRoot());
        configureCropView();
        binding.cancelCrop.setOnClickListener(view -> cancel());
        binding.usePhoto.setOnClickListener(view -> exportCrop());
        loadSource(getIntent().getData());
    }

    private void configureCropView() {
        binding.cropImage.setFixedAspectRatio(true);
        binding.cropImage.setAspectRatio(1, 1);
        binding.cropImage.setCropShape(CropImageView.CropShape.OVAL);
        binding.cropImage.setGuidelines(CropImageView.Guidelines.ON);
        binding.cropImage.setOnSetImageUriCompleteListener((view, uri, error) -> {
            setBusy(false);
            if (error == null) {
                binding.usePhoto.setEnabled(true);
            } else {
                showError();
            }
        });
        binding.cropImage.setOnCropImageCompleteListener((view, result) -> completeCrop(result));
    }

    private void loadSource(Uri source) {
        if (source == null) {
            showError();
            return;
        }
        setBusy(true);
        binding.cropImage.setImageUriAsync(source);
    }

    private void exportCrop() {
        try {
            outputFile = createOutputFile();
            Uri outputUri = FileProvider.getUriForFile(
                    this, getPackageName() + ".cropper.fileprovider", outputFile);
            setBusy(true);
            binding.cropImage.croppedImageAsync(
                    webpFormat(),
                    88,
                    512,
                    512,
                    CropImageView.RequestSizeOptions.RESIZE_EXACT,
                    outputUri);
        } catch (IOException | RuntimeException failure) {
            cleanupOutput();
            showError();
        }
    }

    private void completeCrop(CropImageView.CropResult result) {
        setBusy(false);
        Uri uri = result.getUriContent();
        if (!result.isSuccessful() || uri == null || outputFile == null || !outputFile.isFile()) {
            cleanupOutput();
            showError();
            return;
        }
        resultDelivered = true;
        Intent data = new Intent().setData(uri).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
        setResult(Activity.RESULT_OK, data);
        finish();
    }

    private File createOutputFile() throws IOException {
        File directory = new File(getCacheDir(), OUTPUT_DIRECTORY);
        if (!directory.isDirectory() && !directory.mkdirs()) {
            throw new IOException("Could not prepare crop cache");
        }
        return File.createTempFile("profile-", ".webp", directory);
    }

    private void setBusy(boolean busy) {
        binding.cropProgress.setVisibility(busy ? View.VISIBLE : View.GONE);
        binding.usePhoto.setEnabled(!busy && binding.cropImage.getImageUri() != null);
    }

    private void showError() {
        setBusy(false);
        binding.usePhoto.setEnabled(false);
        binding.cropStatus.setText(R.string.photo_crop_failed);
    }

    private void cancel() {
        cleanupOutput();
        setResult(Activity.RESULT_CANCELED);
        finish();
    }

    private void cleanupOutput() {
        if (outputFile != null && outputFile.isFile() && !outputFile.delete()) {
            Log.w(TAG, "Could not remove temporary crop output");
        }
        outputFile = null;
    }

    @SuppressWarnings("deprecation")
    private static Bitmap.CompressFormat webpFormat() {
        return Build.VERSION.SDK_INT >= Build.VERSION_CODES.R
                ? Bitmap.CompressFormat.WEBP_LOSSY
                : Bitmap.CompressFormat.WEBP;
    }

    @Override
    protected void onDestroy() {
        if (isFinishing() && !resultDelivered) cleanupOutput();
        super.onDestroy();
    }
}
