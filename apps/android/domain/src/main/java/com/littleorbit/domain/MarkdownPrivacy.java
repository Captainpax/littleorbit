package com.littleorbit.domain;

import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** Privacy transform applied before rendering shared Markdown on a device. */
public final class MarkdownPrivacy {
    private static final Pattern REMOTE_IMAGE = Pattern.compile(
            "!\\[([^]]*)]\\((https?://[^)\\s]+)(?:\\s+\"[^\"]*\")?\\)");
    private static final Pattern RAW_HTML = Pattern.compile(
            "<(/?[A-Za-z][^>]{0,500})>");

    private MarkdownPrivacy() {}

    /** Blocks automatic remote image requests and raw HTML outside fenced code. */
    public static String forPreview(String markdown) {
        StringBuilder output = new StringBuilder(markdown.length() + 64);
        boolean fenced = false;
        String[] lines = markdown.split("\n", -1);
        for (int index = 0; index < lines.length; index++) {
            String line = lines[index];
            if (line.stripLeading().startsWith("```")) fenced = !fenced;
            output.append(fenced ? line : sanitizeLine(line));
            if (index < lines.length - 1) output.append('\n');
        }
        return output.toString();
    }

    private static String sanitizeLine(String line) {
        Matcher images = REMOTE_IMAGE.matcher(line);
        StringBuffer blocked = new StringBuffer(line.length() + 32);
        while (images.find()) {
            String replacement = "[Remote image blocked: " + safeAlt(images.group(1))
                    + "](" + images.group(2) + ")";
            images.appendReplacement(blocked, Matcher.quoteReplacement(replacement));
        }
        images.appendTail(blocked);
        return RAW_HTML.matcher(blocked.toString()).replaceAll("&lt;$1&gt;");
    }

    private static String safeAlt(String value) {
        return value.isBlank() ? "tap to open" : value.replace("]", "");
    }
}
