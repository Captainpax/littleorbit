package com.littleorbit.mobile;

import java.io.File;
import java.io.IOException;

/** Fixed-authority source used by installer verification and Kadb package operations. */
interface TrustedWearArtifactSource {
    WearReleaseMetadata metadata() throws IOException;

    File download(WearReleaseMetadata release) throws IOException;
}
