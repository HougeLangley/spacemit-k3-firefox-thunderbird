# SpacemiT K3 Firefox 160.0 / Thunderbird 160.0 — pre-release

Ubuntu 26.04 `riscv64` packages for SpacemiT K3, built with clang 24.

This is a **pre-release** for testing, not a declaration that all K3 media issues are fixed.

## Packages

| Package | Version | SHA256 |
|---|---|---|
| Firefox | `160.0+build1-0ubuntu0.26.04.1~mt1k3.6` | `9276cc5b53a0609d6919fb3c9f8174c6e527471cc080da61d284dfb996859294` |
| Thunderbird | `1:160.0-1k3.1` | `53460aae7f4454db32c176d75a76ae3358f76b8129df4529ec1c67271eb195cb` |

Verify downloads against `SHA256SUMS` before installation. The remote Firefox asset and the local 1.6 deb have the same size (86,866,304 bytes) and SHA256.

## Firefox media behavior

- Local Firefox 1.6 disables `media.hardware-video-decoding.enabled` in `/etc/firefox/syspref.js` as a fallback for repeated K3 MPP error frames.
- PPA source 1.5 contains `k3-v4l2-codec-filter.patch`, retaining H.264/HEVC V4L2 while excluding VP8/VP9/AV1 V4L2 selection. As of `2026-11-19T00:03:23Z`, PPA build `33984218` is still `Needs building`; no Firefox PPA binary has been published.
- YouTube high-resolution playback can still drop frames or stall. Controlled default-JIT versus Ion/Warp-disabled tests did not demonstrate a JIT fix. This package does **not** change RISC-V JIT source or JIT thresholds.
- Final binary scans show substantial RVV instructions, but IME1 `vmadot=0` and IME2 `vfwmadot=0`; IME acceleration kernels are not included.

## Installation note

Install the downloaded `.deb` explicitly and verify `firefox --version` / `thunderbird --version` afterwards. If Ubuntu's snap transition package has a higher epoch, selecting the desired local deb/version may require an explicit apt version choice; do not assume a plain `apt upgrade` selects this pre-release.
