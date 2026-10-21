"""API binding for the AI package's content-free, physical-device proof protocol."""

from little_orbit_ai.gpu_probe import (
    AmdProbeIdentity,
    GpuReleaseUnsafe,
    GpuRequirement,
    request_idle_proof,
)

from .config import Settings

__all__ = ["GpuReleaseUnsafe", "request_idle_proof"]


def gpu_requirement(settings: Settings) -> GpuRequirement | None:
    if settings.gpu_probe_backend != "amd-vulkan":
        return None
    if (
        settings.gpu_amd_pci_bdf is None
        or settings.gpu_amd_device_id is None
        or settings.gpu_amd_render_major is None
        or settings.gpu_amd_render_minor is None
        or settings.gpu_amd_idle_vram_bytes is None
    ):
        raise RuntimeError("AMD GPU admission is incomplete")
    identity = AmdProbeIdentity(
        settings.gpu_amd_pci_bdf,
        settings.gpu_amd_device_id,
        settings.gpu_amd_render_major,
        settings.gpu_amd_render_minor,
        settings.gpu_amd_idle_vram_bytes,
    )
    return GpuRequirement(settings.gpu_amd_probe_socket, identity, settings.gpu_recovery_proof_mode)
