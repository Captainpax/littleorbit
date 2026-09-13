# Third-party notices

Little Orbit is MIT-licensed application code and depends on separately licensed open-source components. Their licenses remain controlling for those components. The dependency lockfiles and build files are the exact version source of truth.

The Android client directly relies on:

- [Kadb 2.1.4](https://github.com/flyfishxu/Kadb), Apache License 2.0, for user-driven local wireless-ADB pairing and Wear APK installation.
- [Conscrypt 2.6.0](https://github.com/google/conscrypt), Apache License 2.0, for the public TLS exporter used by Android wireless-debug pairing.
- [Android Image Cropper 4.7.0](https://github.com/CanHub/Android-Image-Cropper), Apache License 2.0, for the phone's explicit square photo crop.
- [Pillow 11.3.0](https://python-pillow.github.io/), HPND License, for server-side image decoding, orientation, metadata removal, resizing, and WebP encoding.

The Android build also includes Kotlin runtime and cryptography/network transitive dependencies required by Kadb. Little Orbit authors no production Kotlin source. RC10.1 excludes Kadb's optional HiddenApiBypass dependency and packages Conscrypt native libraries with 16 KiB page alignment. Redistributors should generate a complete dependency and license report from the pinned build before distributing binaries.
