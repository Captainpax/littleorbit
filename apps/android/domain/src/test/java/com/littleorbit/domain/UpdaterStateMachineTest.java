package com.littleorbit.domain;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.junit.jupiter.api.Test;

/** Verifies restart-safe update phases and retry preservation. */
public final class UpdaterStateMachineTest {
    @Test
    public void installRetryRetainsExactReleaseAndVerifiedBytes() {
        UpdaterStateMachine machine = new UpdaterStateMachine();
        machine.select("3:abc", true);
        machine.downloading(50, 100);
        machine.verifying(100);
        UpdaterStateMachine.Snapshot retry = machine.retryInstall("install_cancelled", 100);

        assertEquals("3:abc", retry.releaseId());
        assertEquals(UpdaterStateMachine.RETRY_INSTALL, retry.phase());
        assertEquals(100, retry.downloadedBytes());
        assertTrue(retry.required());
    }

    @Test
    public void unknownPersistedPhaseFailsBackToIdle() {
        UpdaterStateMachine machine = new UpdaterStateMachine(
                new UpdaterStateMachine.Snapshot("injected", "x", "", 4, 4, true));
        assertEquals(UpdaterStateMachine.IDLE, machine.snapshot().phase());
    }

    @Test
    public void sameReleaseSurvivesRestartAndCanEscalateToRequired() {
        UpdaterStateMachine machine = new UpdaterStateMachine();
        machine.select("3:abc", false);
        machine.downloading(40, 100);

        UpdaterStateMachine.Snapshot restored = new UpdaterStateMachine(machine.snapshot())
                .selectPreservingWork("3:abc", true);

        assertEquals(UpdaterStateMachine.DOWNLOADING, restored.phase());
        assertEquals(40, restored.downloadedBytes());
        assertTrue(restored.required());
    }

    @Test
    public void differentReleaseDoesNotReuseOldDownloadState() {
        UpdaterStateMachine machine = new UpdaterStateMachine();
        machine.select("2:old", false);
        machine.verifying(100);

        UpdaterStateMachine.Snapshot replacement =
                machine.selectPreservingWork("3:new", false);

        assertEquals(UpdaterStateMachine.AVAILABLE, replacement.phase());
        assertEquals("3:new", replacement.releaseId());
        assertEquals(0, replacement.downloadedBytes());
    }
}
