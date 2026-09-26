package com.littleorbit.domain;

/** One minimal UTF-16 text replacement with cursor mapping across Unicode edits. */
public record TextPatch(int start, int end, String replacement, int newLength) {
    /** Calculates the smallest safe replacement between two immutable bodies. */
    public static TextPatch between(String oldText, String newText) {
        int[] oldPoints = oldText.codePoints().toArray();
        int[] newPoints = newText.codePoints().toArray();
        int prefix = commonPrefix(oldPoints, newPoints);
        int suffix = commonSuffix(oldPoints, newPoints, prefix);
        int oldStart = oldText.offsetByCodePoints(0, prefix);
        int oldEnd = oldText.offsetByCodePoints(0, oldPoints.length - suffix);
        int newStart = newText.offsetByCodePoints(0, prefix);
        int newEnd = newText.offsetByCodePoints(0, newPoints.length - suffix);
        return new TextPatch(
                oldStart, oldEnd, newText.substring(newStart, newEnd), newText.length());
    }

    /** Maps one prior selection endpoint through this replacement. */
    public int mapOffset(int offset) {
        int mapped;
        if (offset <= start) {
            mapped = offset;
        } else if (offset >= end) {
            mapped = offset + replacement.length() - (end - start);
        } else {
            mapped = start + replacement.length();
        }
        return Math.max(0, Math.min(mapped, newLength));
    }

    /** Returns whether the texts are already equal. */
    public boolean isEmpty() {
        return start == end && replacement.isEmpty();
    }

    private static int commonPrefix(int[] first, int[] second) {
        int result = 0;
        while (result < first.length
                && result < second.length
                && first[result] == second[result]) {
            result++;
        }
        return result;
    }

    private static int commonSuffix(int[] first, int[] second, int prefix) {
        int result = 0;
        while (result < first.length - prefix
                && result < second.length - prefix
                && first[first.length - result - 1] == second[second.length - result - 1]) {
            result++;
        }
        return result;
    }
}
