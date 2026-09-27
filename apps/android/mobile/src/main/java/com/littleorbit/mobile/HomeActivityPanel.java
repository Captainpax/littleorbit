package com.littleorbit.mobile;

import androidx.appcompat.app.AppCompatActivity;
import com.littleorbit.data.remote.ActivityApiModels;
import com.littleorbit.data.repository.OrbitRepository;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import java.util.function.Consumer;

/** Owns Home's privacy-minimized activity rendering and seen watermark. */
public final class HomeActivityPanel {
    private final MainActivity activity;
    private final OrbitRepository orbit;
    private final Consumer<List<OrbitShellActivity.ContextAction>> renderer;
    private final Consumer<Class<? extends AppCompatActivity>> navigator;
    private long visibleSequence;

    /** Connects authorized feed data to the Home context drawer. */
    public HomeActivityPanel(
            MainActivity activity,
            OrbitRepository orbit,
            Consumer<List<OrbitShellActivity.ContextAction>> renderer,
            Consumer<Class<? extends AppCompatActivity>> navigator) {
        this.activity = activity;
        this.orbit = orbit;
        this.renderer = renderer;
        this.navigator = navigator;
    }

    /** Loads the newest authorized events without blocking Home rendering. */
    public void refresh() {
        orbit.activity().thenAccept(page -> activity.runOnUiThread(() -> render(page)))
                .exceptionally(failure -> null);
    }

    /** Advances the monotonic watermark only after the panel is opened. */
    public void markVisibleSeen() {
        if (visibleSequence <= 0) return;
        orbit.markActivitySeen(visibleSequence, UUID.randomUUID().toString())
                .exceptionally(failure -> null);
    }

    private void render(ActivityApiModels.Page page) {
        ArrayList<OrbitShellActivity.ContextAction> actions = new ArrayList<>();
        visibleSequence = 0;
        for (ActivityApiModels.Event event : page.items) {
            visibleSequence = Math.max(visibleSequence, event.sequence);
            actions.add(new OrbitShellActivity.ContextAction(label(event), () -> open(event)));
        }
        renderer.accept(actions);
    }

    private String label(ActivityApiModels.Event event) {
        String target = event.targetTitle == null ? "" : " · " + event.targetTitle;
        return switch (event.kind) {
            case "note_created" -> event.partnerDisplayName + " created a note" + target;
            case "note_updated" -> event.partnerDisplayName + " updated a note" + target;
            case "attachment_available" -> "An attachment is ready to insert";
            case "smooch_received" -> event.partnerDisplayName + " sent a Smooch "
                    + (event.emoji == null ? "" : event.emoji);
            case "countdown_created" -> event.partnerDisplayName + " added" + target;
            case "countdown_updated" -> event.partnerDisplayName + " updated" + target;
            case "quiz_submitted" -> event.partnerDisplayName + " finished the quiz";
            case "relationship_name_changed" ->
                    event.partnerDisplayName + " updated a shared name";
            case "quiz_revealed" -> "Your quiz answers are ready together";
            default -> "Your shared orbit changed";
        };
    }

    private void open(ActivityApiModels.Event event) {
        if ("note".equals(event.targetType)) navigator.accept(NotesActivity.class);
        else if ("countdown".equals(event.targetType)) navigator.accept(CountdownActivity.class);
        else if ("quiz".equals(event.targetType)) navigator.accept(QuizActivity.class);
        else if ("smooch".equals(event.targetType)) navigator.accept(SmoochActivity.class);
    }
}
