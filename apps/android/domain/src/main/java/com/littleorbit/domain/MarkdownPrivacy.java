package com.littleorbit.domain;

import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** Privacy transform applied before rendering shared Markdown on a device. */
public final class MarkdownPrivacy {
    private static final Pattern REMOTE_IMAGE = Pattern.compile(
            "!\\[([^]]*)]\\((https?://[^)\\s]+)(?:\\s+\"[^\"]*\")?\\)");
    private static final Pattern SAFE_AUTOLINK = Pattern.compile(
            "<(?:https://[^ <>]+|mailto:[^ <>]+|"
                    + "[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
                    + "[A-Za-z0-9.-]+\\.[A-Za-z]{2,})>");

    private MarkdownPrivacy() {}

    /** Blocks automatic remote image requests and escapes raw HTML outside code. */
    public static String forPreview(String markdown) {
        StringBuilder output = new StringBuilder(markdown.length() + 64);
        Fence fence = null;
        String[] lines = markdown.split("\n", -1);
        for (int index = 0; index < lines.length; index++) {
            String line = lines[index];
            Fence marker = fenceAtStart(line);
            if (fence == null) {
                output.append(marker == null && !indentedCode(line) ? sanitizeLine(line) : line);
                fence = marker;
            } else {
                output.append(line);
                if (closes(line, fence)) fence = null;
            }
            if (index < lines.length - 1) output.append('\n');
        }
        return output.toString();
    }

    /** Reports whether preview will neutralize raw HTML outside code spans or fences. */
    public static boolean containsRawHtml(String markdown) {
        return !transformHtml(markdown).equals(markdown);
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
        return sanitizeInlineHtml(blocked.toString());
    }

    private static String transformHtml(String markdown) {
        StringBuilder output = new StringBuilder(markdown.length() + 32);
        Fence fence = null;
        String[] lines = markdown.split("\n", -1);
        for (int index = 0; index < lines.length; index++) {
            String line = lines[index];
            Fence marker = fenceAtStart(line);
            if (fence == null) {
                output.append(marker == null && !indentedCode(line)
                        ? sanitizeInlineHtml(line) : line);
                fence = marker;
            } else {
                output.append(line);
                if (closes(line, fence)) fence = null;
            }
            if (index < lines.length - 1) output.append('\n');
        }
        return output.toString();
    }

    private static String sanitizeInlineHtml(String line) {
        StringBuilder output = new StringBuilder(line.length() + 16);
        for (int index = 0; index < line.length(); ) {
            int ticks = runLength(line, index, '`');
            if (ticks > 0) {
                int close = closingTicks(line, index + ticks, ticks);
                int end = close < 0 ? index + ticks : close + ticks;
                output.append(line, index, end);
                index = end;
                continue;
            }
            if (line.charAt(index) == '<') {
                int end = line.indexOf('>', index + 1);
                if (end >= 0 && SAFE_AUTOLINK.matcher(line.substring(index, end + 1)).matches()) {
                    output.append(line, index, end + 1);
                    index = end + 1;
                    continue;
                }
                if (looksLikeHtml(line, index)) {
                    output.append("&lt;");
                    index++;
                    continue;
                }
            }
            output.append(line.charAt(index++));
        }
        return output.toString();
    }

    private static int closingTicks(String line, int start, int length) {
        int position = line.indexOf('`', start);
        while (position >= 0) {
            if (runLength(line, position, '`') == length) return position;
            position = line.indexOf('`', position + 1);
        }
        return -1;
    }

    private static boolean looksLikeHtml(String line, int start) {
        if (start + 1 >= line.length()) return false;
        char next = line.charAt(start + 1);
        if (Character.isLetter(next) || next == '!' || next == '?') return true;
        return next == '/' && start + 2 < line.length()
                && Character.isLetter(line.charAt(start + 2));
    }

    private static Fence fenceAtStart(String line) {
        String leading = line.stripLeading();
        if (leading.isEmpty()) return null;
        char marker = leading.charAt(0);
        if (marker != '`' && marker != '~') return null;
        int count = runLength(leading, 0, marker);
        return count >= 3 ? new Fence(marker, count) : null;
    }

    private static boolean indentedCode(String line) {
        return line.startsWith("    ") || line.startsWith("\t");
    }

    private static boolean closes(String line, Fence fence) {
        String leading = line.stripLeading();
        int count = runLength(leading, 0, fence.marker);
        return count >= fence.length && leading.substring(count).isBlank();
    }

    private static int runLength(String value, int start, char wanted) {
        int end = start;
        while (end < value.length() && value.charAt(end) == wanted) end++;
        return end - start;
    }

    private static String safeAlt(String value) {
        return value.isBlank() ? "tap to open" : value.replace("]", "");
    }

    private record Fence(char marker, int length) {}
}
