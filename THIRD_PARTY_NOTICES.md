# Third-party notices

Little Orbit is MIT-licensed application code and depends on separately licensed open-source components. Their licenses remain controlling for those components. The dependency lockfiles and build files are the exact version source of truth.

RC8 adds or directly relies on:

- [Kadb 2.1.1](https://github.com/Flyfish233/Kadb), Apache License 2.0, for user-driven local wireless-ADB pairing and Wear APK installation.
- [Android Image Cropper 4.7.0](https://github.com/CanHub/Android-Image-Cropper), Apache License 2.0, for the phone's explicit square photo crop.
- [Pillow 11.3.0](https://python-pillow.github.io/), HPND License, for server-side image decoding, orientation, metadata removal, resizing, and WebP encoding.

The Android build also includes Kotlin runtime and cryptography/network transitive dependencies required by Kadb. Little Orbit authors no production Kotlin source. Redistributors should generate a complete dependency and license report from the pinned build before distributing binaries.
