# Candidate only: no host driver, toolkit, daemon, or kernel changes.
FROM ollama/ollama:0.35.1@sha256:17e945f1aa6e505707eeb621e3f36847d0a4a063d4778f7007645acccfb8bd4f

ARG MESA_VULKAN_DRIVERS_VERSION
RUN test -n "$MESA_VULKAN_DRIVERS_VERSION" \
    && apt-get update \
    && apt-get install --yes --no-install-recommends \
       "mesa-vulkan-drivers=$MESA_VULKAN_DRIVERS_VERSION" \
    && test -f /usr/share/vulkan/icd.d/radeon_icd.x86_64.json \
    && rm -rf /var/lib/apt/lists/*

ENV OLLAMA_VULKAN=1 \
    GGML_VK_VISIBLE_DEVICES=0 \
    VK_DRIVER_FILES=/usr/share/vulkan/icd.d/radeon_icd.x86_64.json
