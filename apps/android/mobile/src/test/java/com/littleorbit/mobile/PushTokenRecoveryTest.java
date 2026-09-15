package com.littleorbit.mobile;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNotEquals;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

public final class PushTokenRecoveryTest {
    @Test
    public void digestDoesNotRetainTheRegistrationAddress() {
        String token = "private-fcm-installation-address";

        String digest = PushTokenRecovery.digest(token);

        assertNotEquals(token, digest);
        assertTrue(PushTokenRecovery.matches(digest, token));
        assertFalse(PushTokenRecovery.matches(digest, token + "-rotated"));
    }

    @Test
    public void recoveryAllowsOnlyOneAutomaticRotationUntilAcceptance() {
        String token = "private-fcm-installation-address";

        assertTrue(PushTokenRecovery.shouldRotate(false, null, token));
        assertFalse(PushTokenRecovery.shouldRotate(true, null, token + "-rotated"));
        assertFalse(PushTokenRecovery.shouldRotate(
                false, PushTokenRecovery.digest(token), token));
    }
}
