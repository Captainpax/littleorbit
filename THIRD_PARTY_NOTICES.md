# Third-party notices

Little Orbit is MIT-licensed application code and depends on separately licensed open-source components. Their licenses remain controlling for those components. The dependency lockfiles and build files are the exact version source of truth.

The Android client directly relies on:

- [Kadb 2.1.4](https://github.com/flyfishxu/Kadb), Apache License 2.0, for user-driven local wireless-ADB pairing and Wear APK installation.
- [Conscrypt 2.6.0](https://github.com/google/conscrypt), Apache License 2.0, for the public TLS exporter used by Android wireless-debug pairing.
- [Android Image Cropper 4.7.0](https://github.com/CanHub/Android-Image-Cropper), Apache License 2.0, for the phone's explicit square photo crop.
- [Markwon 4.6.2](https://github.com/noties/Markwon), Apache License 2.0, for native CommonMark and GitHub-style Markdown rendering.
- [android-gif-drawable 1.2.32](https://github.com/koral--/android-gif-drawable), MIT License, for bounded playback of sanitized inline GIF attachments.
- [Pillow 11.3.0](https://python-pillow.github.io/), HPND License, for server-side image decoding, orientation, metadata removal, resizing, and WebP encoding.
- [Psycopg 3.2.10](https://www.psycopg.org/psycopg3/), GNU Lesser General Public License 3.0, for synchronous PostgreSQL migration connections used by Alembic.
- [pypdf 6.0.0](https://github.com/py-pdf/pypdf), BSD-3-Clause License, for rebuilding PDFs without source document metadata.
- [ClamAV 1.4.6](https://www.clamav.net/), GPL-2.0, in an internal container that scans private note attachments before availability.
- [FFmpeg](https://ffmpeg.org/), under the licenses of the Debian package build, for removing source metadata from accepted audio and video containers without transcoding. Redistributors must review the exact packaged configuration and its component licenses.
The Android build also includes Kotlin runtime and cryptography/network transitive dependencies required by Kadb. Little Orbit authors no production Kotlin source. RC10.1 excludes Kadb's optional HiddenApiBypass dependency and packages Conscrypt native libraries with 16 KiB page alignment. Redistributors should generate a complete dependency and license report from the pinned build before distributing binaries.
