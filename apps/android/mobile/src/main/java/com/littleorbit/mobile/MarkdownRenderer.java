package com.littleorbit.mobile;

import android.content.Context;
import android.widget.TextView;
import com.littleorbit.domain.MarkdownPrivacy;
import io.noties.markwon.Markwon;
import io.noties.markwon.ext.strikethrough.StrikethroughPlugin;
import io.noties.markwon.ext.tables.TablePlugin;
import io.noties.markwon.ext.tasklist.TaskListPlugin;
import io.noties.markwon.linkify.LinkifyPlugin;

/** Native TextView Markdown renderer with network-private defaults. */
public final class MarkdownRenderer {
    private final Markwon markwon;

    /** Creates a CommonMark and GFM-style renderer without raw HTML or image loaders. */
    public MarkdownRenderer(Context context) {
        markwon = Markwon.builder(context)
                .usePlugin(StrikethroughPlugin.create())
                .usePlugin(TablePlugin.create(context))
                .usePlugin(TaskListPlugin.create(context))
                .usePlugin(LinkifyPlugin.create())
                .build();
    }

    /** Renders Markdown while converting remote images into deliberate links. */
    public void render(TextView target, String markdown) {
        markwon.setMarkdown(target, MarkdownPrivacy.forPreview(markdown));
    }
}
