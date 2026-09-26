package com.littleorbit.mobile;

/** User-facing wording for server-selected, stable Smooch phrase keys. */
final class SmoochPhrases {
    private SmoochPhrases() {}

    static String render(android.content.Context context, String key, String name, String emoji) {
        int resource = switch (key) {
            case "thinking_about_you" -> R.string.smooch_thinking;
            case "little_love" -> R.string.smooch_little_love;
            case "nudged_your_orbit" -> R.string.smooch_nudged_orbit;
            case "make_you_smile" -> R.string.smooch_make_smile;
            case "tiny_spark" -> R.string.smooch_tiny_spark;
            default -> R.string.smooch_sent;
        };
        return context.getString(resource, name, emoji);
    }
}
