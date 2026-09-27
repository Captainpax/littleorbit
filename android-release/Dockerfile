# syntax=docker/dockerfile:1
FROM eclipse-temurin:17-jdk-jammy@sha256:f9a2d0cf41b61289dd6d92b3af9a17fb6948a8977dd69cc26a61bc2465457929 AS sdk

ARG COMMAND_LINE_TOOLS_URL=https://dl.google.com/android/repository/commandlinetools-linux-14742923_latest.zip
ARG COMMAND_LINE_TOOLS_SHA256=04453066b540409d975c676d781da1477479dde3761310f1a7eb92a1dfb15af7
ENV ANDROID_HOME=/opt/android-sdk \
    ANDROID_SDK_ROOT=/opt/android-sdk \
    PATH=/opt/android-sdk/cmdline-tools/20.0/bin:/opt/android-sdk/build-tools/37.0.0:$PATH

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        ca-certificates curl python3 unzip \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /opt/android-sdk/cmdline-tools \
    && curl --fail --location --silent --show-error "$COMMAND_LINE_TOOLS_URL" -o /tmp/tools.zip \
    && echo "$COMMAND_LINE_TOOLS_SHA256  /tmp/tools.zip" | sha256sum --check --strict \
    && unzip -q /tmp/tools.zip -d /tmp/android-tools \
    && mv /tmp/android-tools/cmdline-tools /opt/android-sdk/cmdline-tools/20.0 \
    && rm -rf /tmp/tools.zip /tmp/android-tools \
    && yes | sdkmanager --licenses >/dev/null \
    && sdkmanager --install "platform-tools" "platforms;android-37.0" "build-tools;37.0.0" \
    && grep -Fx "Pkg.Revision=20.0" /opt/android-sdk/cmdline-tools/20.0/source.properties \
    && grep -Fx "Pkg.Revision=2" /opt/android-sdk/platforms/android-37.0/source.properties \
    && grep -Fx "Pkg.Revision=37.0.0" /opt/android-sdk/build-tools/37.0.0/source.properties

FROM sdk AS builder
COPY release_tool.py policy.json container-build.sh /opt/release/
RUN chmod 0555 /opt/release/container-build.sh \
    && touch /opt/little-orbit-android-builder \
    && chmod 0444 /opt/little-orbit-android-builder
ENV LITTLE_ORBIT_ISOLATED_UNSIGNED_BUILDER=1
ENTRYPOINT ["/opt/release/container-build.sh"]

FROM sdk AS signer
COPY release_tool.py policy.json container-sign.sh container-verify-signer.sh \
    SignerCertificateVerifier.java /opt/release/
RUN javac --release 17 -d /opt/release /opt/release/SignerCertificateVerifier.java \
    && rm /opt/release/SignerCertificateVerifier.java \
    && chmod 0555 /opt/release/container-sign.sh /opt/release/container-verify-signer.sh
ENTRYPOINT ["/opt/release/container-sign.sh"]
