package com.littleorbit.data.remote;

import com.littleorbit.data.security.SessionStore;
import java.io.IOException;
import javax.inject.Inject;
import javax.inject.Singleton;
import okhttp3.Interceptor;
import okhttp3.Request;
import okhttp3.Response;

/** Adds the opaque session only to the fixed Little Orbit API client. */
@Singleton
public final class SessionInterceptor implements Interceptor {
    private final SessionStore sessions;

    /** Creates the interceptor with encrypted token storage. */
    @Inject
    public SessionInterceptor(SessionStore sessions) {
        this.sessions = sessions;
    }

    /** Attaches authorization without logging or copying it into a URL. */
    @Override
    public Response intercept(Chain chain) throws IOException {
        Request request = chain.request();
        String token = sessions.read().orElse(null);
        if (token != null) {
            request = request.newBuilder().header("Authorization", "Bearer " + token).build();
        }
        return chain.proceed(request);
    }
}
