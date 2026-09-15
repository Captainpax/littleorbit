package com.littleorbit.mobile;

import android.content.Context;
import android.content.Intent;
import android.net.Uri;
import android.widget.TextView;
import androidx.annotation.NonNull;
import com.littleorbit.data.remote.NoteApiModels;
import com.littleorbit.data.repository.OrbitRepository;
import com.littleorbit.domain.MarkdownPrivacy;
import io.noties.markwon.AbstractMarkwonPlugin;
import io.noties.markwon.LinkResolver;
import io.noties.markwon.Markwon;
import io.noties.markwon.MarkwonConfiguration;
import io.noties.markwon.ext.strikethrough.StrikethroughPlugin;
import io.noties.markwon.ext.tables.TablePlugin;
import io.noties.markwon.ext.tasklist.TaskListPlugin;
import io.noties.markwon.image.DefaultDownScalingMediaDecoder;
import io.noties.markwon.image.ImageItem;
import io.noties.markwon.image.ImagesPlugin;
import io.noties.markwon.image.SchemeHandler;
import io.noties.markwon.image.gif.GifMediaDecoder;
import io.noties.markwon.linkify.LinkifyPlugin;
import java.io.File;
import java.io.FileInputStream;
import java.util.Collection;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import java.util.function.Consumer;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** Native Markdown renderer that resolves only verified private note attachments. */
public final class MarkdownRenderer {
    private static final Pattern ATTACHMENT_IMAGE = Pattern.compile(
            "(?<!\\[)!\\[([^]]*)]\\(attachment://([0-9a-fA-F-]{36})\\)");
    private static final Collection<String> IMAGE_TYPES = List.of(
            "image/jpeg", "image/png", "image/webp", "image/gif");
    // Markwon otherwise creates an unbounded cached pool for document images.
    private static final ExecutorService IMAGE_EXECUTOR = Executors.newFixedThreadPool(2, task -> {
        Thread thread = new Thread(task, "orbit-markdown-image");
        thread.setDaemon(true);
        return thread;
    });
    private final Context context;
    private final OrbitRepository orbit;
    private final Consumer<NoteApiModels.Attachment> attachmentOpened;
    private final Markwon markwon;
    private volatile State state = State.empty();
    private TextView renderedTarget;

    /** Creates a CommonMark/GFM renderer with no remote, file, or data image loaders. */
    public MarkdownRenderer(
            Context context,
            OrbitRepository orbit,
            Consumer<NoteApiModels.Attachment> attachmentOpened) {
        this.context = context;
        this.orbit = orbit;
        this.attachmentOpened = attachmentOpened;
        ImagesPlugin images = ImagesPlugin.create(plugin -> plugin
                .executorService(IMAGE_EXECUTOR)
                .removeSchemeHandler("http")
                .removeSchemeHandler("https")
                .removeSchemeHandler("data")
                .addSchemeHandler(new AttachmentScheme())
                .addMediaDecoder(GifMediaDecoder.create(true))
                .defaultMediaDecoder(DefaultDownScalingMediaDecoder.create(
                        context.getResources(), maxWidth(context), maxHeight(context))));
        markwon = Markwon.builder(context)
                .usePlugin(StrikethroughPlugin.create())
                .usePlugin(TablePlugin.create(context))
                .usePlugin(TaskListPlugin.create(context))
                .usePlugin(LinkifyPlugin.create())
                .usePlugin(images)
                .usePlugin(new SafeLinks())
                .build();
    }

    /** Replaces the exact note-scoped allowlist used by asynchronous image requests. */
    public void setAttachments(String noteId, List<NoteApiModels.Attachment> attachments) {
        setAttachments(null, noteId, attachments);
    }

    /** Uses the former-pairing download boundary for one immutable archive note. */
    public void setArchiveAttachments(
            String archiveId, String noteId, List<NoteApiModels.Attachment> attachments) {
        setAttachments(archiveId, noteId, attachments);
    }

    private void setAttachments(
            String archiveId, String noteId, List<NoteApiModels.Attachment> attachments) {
        Map<String, NoteApiModels.Attachment> allowed = new HashMap<>();
        for (NoteApiModels.Attachment item : attachments) {
            if ("available".equals(item.status) && IMAGE_TYPES.contains(item.mediaType)) {
                allowed.put(item.id, item);
            }
        }
        cancelRenderedImages();
        state = new State(archiveId, noteId, Map.copyOf(allowed));
    }

    /** Immediately drops the note-scoped image allowlist when the editor changes context. */
    public void clearAttachments() {
        cancelRenderedImages();
        state = State.empty();
    }

    /** Renders Markdown and wraps legacy attachment images in safe preview links. */
    public void render(TextView target, String markdown) {
        String privateMarkdown = MarkdownPrivacy.forPreview(markdown);
        renderedTarget = target;
        markwon.setMarkdown(target, clickableAvailableImages(privateMarkdown));
    }

    /** Unschedules animated drawables when preview leaves the visible mode. */
    public void clear(TextView target) {
        markwon.setMarkdown(target, "");
        if (target == renderedTarget) renderedTarget = null;
    }

    private String clickableAvailableImages(String markdown) {
        return clickableAvailableImages(markdown, state.attachments.keySet());
    }

    static String clickableAvailableImages(String markdown, Collection<String> allowedIds) {
        Matcher matcher = ATTACHMENT_IMAGE.matcher(markdown);
        StringBuffer result = new StringBuffer();
        while (matcher.find()) {
            String id = matcher.group(2);
            String replacement = allowedIds.contains(id)
                    ? "[" + matcher.group() + "](attachment://" + id + ")"
                    : safeAlt(matcher.group(1));
            matcher.appendReplacement(result, Matcher.quoteReplacement(replacement));
        }
        matcher.appendTail(result);
        return result.toString();
    }

    private void cancelRenderedImages() {
        TextView target = renderedTarget;
        if (target == null) return;
        renderedTarget = null;
        markwon.setMarkdown(target, "");
    }

    private static String safeAlt(String value) {
        return value.replaceAll("[\\[\\]\\(\\)!\\r\\n]", " ")
                .replaceAll("\\s+", " ")
                .trim();
    }

    private static int maxWidth(Context context) {
        return Math.min(context.getResources().getDisplayMetrics().widthPixels, 1600);
    }

    private static int maxHeight(Context context) {
        return Math.min(context.getResources().getDisplayMetrics().heightPixels * 2, 2400);
    }

    private final class AttachmentScheme extends SchemeHandler {
        @NonNull @Override public ImageItem handle(@NonNull String raw, @NonNull Uri uri) {
            String id = uri.getHost();
            State snapshot = state;
            NoteApiModels.Attachment item = id == null ? null : snapshot.attachments.get(id);
            if (item == null || snapshot.noteId == null) {
                throw new IllegalArgumentException("Attachment is unavailable");
            }
            try {
                File file = download(snapshot, item);
                return ImageItem.withDecodingNeeded(item.mediaType, new FileInputStream(file));
            } catch (Exception failure) {
                throw new IllegalStateException("Verified attachment could not be loaded", failure);
            }
        }

        private File download(State snapshot, NoteApiModels.Attachment item) throws Exception {
            if (snapshot.archiveId == null) {
                return orbit.downloadNoteAttachment(snapshot.noteId, item)
                        .get(35, TimeUnit.SECONDS);
            }
            return orbit.downloadArchiveAttachment(snapshot.archiveId, snapshot.noteId, item)
                    .get(35, TimeUnit.SECONDS);
        }

        @NonNull @Override public Collection<String> supportedSchemes() {
            return Collections.singleton("attachment");
        }
    }

    private final class SafeLinks extends AbstractMarkwonPlugin {
        @Override public void configureConfiguration(
                @NonNull MarkwonConfiguration.Builder builder) {
            builder.linkResolver(new PrivateLinkResolver());
        }
    }

    private final class PrivateLinkResolver implements LinkResolver {
        @Override public void resolve(@NonNull android.view.View view, @NonNull String link) {
            Uri uri = Uri.parse(link);
            if ("attachment".equals(uri.getScheme())) {
                NoteApiModels.Attachment item = state.attachments.get(uri.getHost());
                if (item != null) attachmentOpened.accept(item);
                return;
            }
            if (!"https".equals(uri.getScheme())) return;
            try {
                context.startActivity(new Intent(Intent.ACTION_VIEW, uri));
            } catch (RuntimeException ignored) {
                // A missing browser leaves the deliberate link inert.
            }
        }
    }

    private record State(
            String archiveId,
            String noteId,
            Map<String, NoteApiModels.Attachment> attachments) {
        static State empty() { return new State(null, null, Map.of()); }
    }
}
