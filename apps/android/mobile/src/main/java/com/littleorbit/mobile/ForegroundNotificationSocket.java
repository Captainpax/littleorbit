package com.littleorbit.mobile;

import android.content.Context;
import com.littleorbit.data.BuildConfig;
import com.littleorbit.data.remote.NotificationApiModels;
import com.littleorbit.data.repository.OrbitRepository;
import dagger.hilt.android.qualifiers.ApplicationContext;
import javax.inject.Inject;
import javax.inject.Singleton;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.Response;
import okhttp3.WebSocket;
import okhttp3.WebSocketListener;

/** Foreground-only WSS hint that prompts the durable WorkManager delivery path. */
@Singleton
public final class ForegroundNotificationSocket {
    private final Context context;
    private final OkHttpClient client;
    private final OrbitRepository orbit;
    private final NotificationDeviceStore device;
    private WebSocket socket;
    private long generation;

    /** Creates a content-free socket client using the authenticated first-party HTTP client. */
    @Inject
    public ForegroundNotificationSocket(
            @ApplicationContext Context context,
            OkHttpClient client,
            OrbitRepository orbit,
            NotificationDeviceStore device) {
        this.context = context;
        this.client = client;
        this.orbit = orbit;
        this.device = device;
    }

    /** Registers this install, opens a foreground hint channel, and starts one immediate poll. */
    public synchronized void open() {
        close();
        if (!orbit.isSignedIn()) return;
        long requested = ++generation;
        boolean enabled = PermissionChecks.notificationsGranted(context);
        orbit.registerNotificationDevice(device.id(),
                new NotificationApiModels.DeviceUpsert(
                        com.littleorbit.mobile.BuildConfig.VERSION_CODE,
                        enabled))
                .thenRun(() -> connect(requested))
                .exceptionally(failure -> {
                    device.failed("Foreground connection will use scheduled checks");
                    return null;
                });
        PartnerNotificationWorker.enqueue(context);
    }

    /** Closes the socket when no Little Orbit activity is visible. */
    public synchronized void close() {
        generation++;
        if (socket != null) socket.close(1000, "background");
        socket = null;
    }

    private synchronized void connect(long requested) {
        if (requested != generation || !orbit.isSignedIn()) return;
        Request request = new Request.Builder()
                .url(BuildConfig.WS_BASE_URL + "ws/v1/notifications?device_id=" + device.id())
                .build();
        socket = client.newWebSocket(request, new HintListener(requested));
    }

    private final class HintListener extends WebSocketListener {
        private final long requested;

        HintListener(long requested) {
            this.requested = requested;
        }

        @Override public void onMessage(WebSocket webSocket, String text) {
            if (text.contains("notification.available")) {
                PartnerNotificationWorker.enqueue(context);
            }
        }

        @Override public void onFailure(WebSocket webSocket, Throwable failure, Response response) {
            synchronized (ForegroundNotificationSocket.this) {
                if (requested == generation && socket == webSocket) socket = null;
            }
        }
    }
}
