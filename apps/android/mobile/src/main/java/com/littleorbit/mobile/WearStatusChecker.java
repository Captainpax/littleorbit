package com.littleorbit.mobile;

import android.content.Context;
import com.google.android.gms.wearable.CapabilityClient;
import com.google.android.gms.wearable.Wearable;
import dagger.hilt.android.qualifiers.ApplicationContext;
import java.util.concurrent.CompletableFuture;
import javax.inject.Inject;
import javax.inject.Singleton;

/** Distinguishes a connected watch from a connected watch running Little Orbit. */
@Singleton
public final class WearStatusChecker {
    private static final String CAPABILITY = "little_orbit_display_v2";
    private final Context context;

    /** Creates the paired-device status boundary. */
    @Inject
    public WearStatusChecker(@ApplicationContext Context context) {
        this.context = context;
    }

    /** Resolves current connected-node and installed-capability state. */
    public CompletableFuture<State> check() {
        CompletableFuture<State> result = new CompletableFuture<>();
        Wearable.getNodeClient(context).getConnectedNodes()
                .addOnFailureListener(failure -> result.complete(State.UNAVAILABLE))
                .addOnSuccessListener(nodes -> {
                    if (nodes.isEmpty()) {
                        result.complete(State.NO_WATCH);
                        return;
                    }
                    Wearable.getCapabilityClient(context)
                            .getCapability(CAPABILITY, CapabilityClient.FILTER_REACHABLE)
                            .addOnFailureListener(failure -> result.complete(State.UNAVAILABLE))
                            .addOnSuccessListener(capability -> result.complete(
                                    capability.getNodes().isEmpty()
                                            ? State.APP_MISSING
                                            : State.APP_CONNECTED));
                });
        return result;
    }

    /** Privacy-safe watch connectivity states rendered by setup surfaces. */
    public enum State {
        NO_WATCH,
        APP_MISSING,
        APP_CONNECTED,
        UNAVAILABLE
    }
}
