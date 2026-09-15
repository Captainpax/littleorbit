package com.littleorbit.mobile;

import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Matrix;
import android.graphics.pdf.PdfRenderer;
import android.os.ParcelFileDescriptor;
import android.view.View;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.MediaController;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.VideoView;
import androidx.appcompat.app.AlertDialog;
import com.google.android.material.dialog.MaterialAlertDialogBuilder;
import com.littleorbit.data.remote.NoteApiModels;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;

/** Shows verified private attachments without granting their URI to another app. */
public final class PrivateAttachmentPreview {
    private static final int TEXT_LIMIT_BYTES = 64 * 1024;
    private static final int MAX_IMAGE_EDGE = 1600;
    private final InsetAwareActivity activity;

    /** Creates an in-app preview presenter bound to one visible activity. */
    public PrivateAttachmentPreview(InsetAwareActivity activity) {
        this.activity = activity;
    }

    /** Opens the best bounded preview supported for one sanitized local file. */
    public void show(File file, NoteApiModels.Attachment attachment) {
        VideoView[] playback = new VideoView[1];
        View content = content(file, attachment, playback);
        AlertDialog dialog = new MaterialAlertDialogBuilder(activity)
                .setTitle(attachment.fileName)
                .setView(content)
                .setPositiveButton(R.string.close, null)
                .create();
        dialog.setOnDismissListener(ignored -> {
            if (playback[0] != null) playback[0].stopPlayback();
        });
        dialog.show();
    }

    private View content(
            File file, NoteApiModels.Attachment attachment, VideoView[] playback) {
        try {
            if (attachment.mediaType.startsWith("image/")) return image(file, attachment.fileName);
            if ("application/pdf".equals(attachment.mediaType)) return pdf(file);
            if (attachment.mediaType.startsWith("text/")) return text(file);
            if (attachment.mediaType.startsWith("audio/")
                    || attachment.mediaType.startsWith("video/")) {
                return media(file, attachment.mediaType, playback);
            }
        } catch (IOException | RuntimeException ignored) {
            return failure();
        }
        return failure();
    }

    private View image(File file, String description) {
        BitmapFactory.Options bounds = new BitmapFactory.Options();
        bounds.inJustDecodeBounds = true;
        BitmapFactory.decodeFile(file.getAbsolutePath(), bounds);
        BitmapFactory.Options options = new BitmapFactory.Options();
        options.inSampleSize = sampleSize(bounds.outWidth, bounds.outHeight);
        Bitmap bitmap = BitmapFactory.decodeFile(file.getAbsolutePath(), options);
        if (bitmap == null) return failure();
        ImageView image = new ImageView(activity);
        image.setAdjustViewBounds(true);
        image.setScaleType(ImageView.ScaleType.FIT_CENTER);
        image.setContentDescription(description);
        image.setImageBitmap(bitmap);
        image.setPadding(dp(8), dp(8), dp(8), dp(8));
        return image;
    }

    private int sampleSize(int width, int height) {
        int sample = 1;
        while (width / sample > MAX_IMAGE_EDGE || height / sample > MAX_IMAGE_EDGE) sample *= 2;
        return sample;
    }

    private View pdf(File file) throws IOException {
        try (ParcelFileDescriptor descriptor =
                        ParcelFileDescriptor.open(file, ParcelFileDescriptor.MODE_READ_ONLY);
                PdfRenderer renderer = new PdfRenderer(descriptor);
                PdfRenderer.Page page = renderer.openPage(0)) {
            float scale = Math.min(
                    (float) MAX_IMAGE_EDGE / Math.max(page.getWidth(), 1),
                    (float) MAX_IMAGE_EDGE / Math.max(page.getHeight(), 1));
            scale = Math.min(scale, 1f);
            int width = Math.max(1, Math.round(page.getWidth() * scale));
            int height = Math.max(1, Math.round(page.getHeight() * scale));
            Bitmap bitmap = Bitmap.createBitmap(width, height, Bitmap.Config.ARGB_8888);
            bitmap.eraseColor(activity.getColor(android.R.color.white));
            Matrix transform = new Matrix();
            transform.setScale(scale, scale);
            page.render(bitmap, null, transform, PdfRenderer.Page.RENDER_MODE_FOR_DISPLAY);
            ImageView image = new ImageView(activity);
            image.setAdjustViewBounds(true);
            image.setContentDescription(activity.getString(R.string.pdf_first_page));
            image.setImageBitmap(bitmap);
            return image;
        }
    }

    private View text(File file) throws IOException {
        byte[] bytes = readPreview(file);
        TextView value = label(new String(bytes, StandardCharsets.UTF_8));
        if (file.length() > bytes.length) value.append(activity.getString(R.string.preview_truncated));
        value.setTextIsSelectable(true);
        value.setPadding(dp(20), dp(12), dp(20), dp(12));
        ScrollView scroll = new ScrollView(activity);
        scroll.addView(value);
        return scroll;
    }

    private byte[] readPreview(File file) throws IOException {
        try (FileInputStream input = new FileInputStream(file);
                ByteArrayOutputStream output = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[8192];
            int remaining = TEXT_LIMIT_BYTES;
            while (remaining > 0) {
                int count = input.read(buffer, 0, Math.min(buffer.length, remaining));
                if (count < 0) break;
                if (count == 0) continue;
                output.write(buffer, 0, count);
                remaining -= count;
            }
            return output.toByteArray();
        }
    }

    private View media(File file, String mediaType, VideoView[] playback) {
        LinearLayout content = new LinearLayout(activity);
        content.setOrientation(LinearLayout.VERTICAL);
        TextView hint = label(activity.getString(
                mediaType.startsWith("audio/")
                        ? R.string.audio_preview_hint
                        : R.string.video_preview_hint));
        hint.setPadding(dp(20), dp(12), dp(20), dp(8));
        content.addView(hint);
        VideoView player = new VideoView(activity);
        playback[0] = player;
        player.setMinimumHeight(dp(mediaType.startsWith("audio/") ? 96 : 240));
        MediaController controls = new MediaController(activity);
        player.setMediaController(controls);
        player.setVideoPath(file.getAbsolutePath());
        player.setOnPreparedListener(media -> controls.show(0));
        player.setOnErrorListener((media, what, extra) -> {
            hint.setText(R.string.attachment_preview_failed);
            return true;
        });
        content.addView(player, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT));
        return content;
    }

    private TextView failure() {
        TextView view = label(activity.getString(R.string.attachment_preview_failed));
        view.setPadding(dp(20), dp(16), dp(20), dp(16));
        return view;
    }

    private TextView label(String value) {
        TextView view = new TextView(activity);
        view.setText(value);
        view.setTextColor(activity.getColor(R.color.cloud));
        view.setTextSize(16);
        return view;
    }

    private int dp(int value) {
        return Math.round(value * activity.getResources().getDisplayMetrics().density);
    }
}
