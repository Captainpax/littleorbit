package com.littleorbit.mobile;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import android.content.Context;
import android.text.Spanned;
import android.text.style.ClickableSpan;
import android.text.style.StrikethroughSpan;
import android.widget.TextView;
import androidx.test.core.app.ApplicationProvider;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import io.noties.markwon.ext.tables.TableRowSpan;
import org.junit.Test;
import org.junit.runner.RunWith;

/** On-device rendering coverage for the supported safe CommonMark/GFM surface. */
@RunWith(AndroidJUnit4.class)
public final class MarkdownRendererInstrumentedTest {
    @Test
    public void previewRendersGfmAndNeutralizesRawHtml() {
        Context context = ApplicationProvider.getApplicationContext();
        TextView[] target = new TextView[1];
        InstrumentationRegistry.getInstrumentation().runOnMainSync(() -> {
            target[0] = new TextView(context);
            MarkdownRenderer renderer = new MarkdownRenderer(context, null, ignored -> {});
            renderer.render(target[0], "| A | B |\n| --- | --- |\n| 1 | 2 |\n"
                    + "- [ ] task\n~~later~~\n<https://example.test>\n"
                    + "```java\nvalue();\n```\n<script>bad()</script>");
        });
        Spanned rendered = (Spanned) target[0].getText();
        String text = rendered.toString();
        assertTrue(rendered.getSpans(0, rendered.length(), TableRowSpan.class).length > 0);
        assertTrue(text.contains("task"));
        assertTrue(text.contains("value();"));
        assertTrue(text.contains("<script>bad()</script>"));
        assertFalse(text.contains("~~later~~"));
        assertTrue(rendered.getSpans(0, rendered.length(), StrikethroughSpan.class).length > 0);
        assertTrue(rendered.getSpans(0, rendered.length(), ClickableSpan.class).length > 0);
    }
}
