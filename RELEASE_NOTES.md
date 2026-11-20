# SpacemiT K3 Firefox 160.0 k3.9 hardware-decode pre-release

Tag: `v160.0-k3.9-20261120`

Ubuntu 26.04 `riscv64` packages for SpacemiT K3. This is a new pre-release,
not an edit of the old hardware-disable/codec-filter releases.

## Packages

| Package | Version | SHA256 |
|---|---|---|
| MPP | `0.1.15+k3.8` | `8f71188822085d9209618621966ad39820d88a3c49b93e05537995440ea1df2b` |
| FFmpeg libavcodec | `7:8.0.1-3ubuntu2bb1k3.2` | `64bbb5dfaa0ce9ebc5bcce44ba0b6f3ac6b4a1266133504bd34473f256494471` |
| Firefox | `160.0+build1-0ubuntu0.26.04.1~mt1k3.9` | `dce19bab115fd8168328d61163a7f09d4cdf0f30c3eda11778d8284b28a973a0` |
| Thunderbird (unchanged compatibility asset) | `1:160.0-1k3.1` | `53460aae7f4454db32c176d75a76ae3358f76b8129df4529ec1c67271eb195cb` |

The release also carries the FFmpeg command-line package and matching runtime
libraries. Verify all eleven assets with `SHA256SUMS` before installation.
Thunderbird was not rebuilt or retested in this MPP/Firefox work.

## What changed

- MPP now handles EOS, concurrent flush/return, stale returns, initialization,
  and repeated HEVC NULL_DATA buffer ownership without deadlocking.
- FFmpeg stcodec no longer discards ten valid frames after each later flush.
- Firefox uses real `h264_stcodec`, `hevc_stcodec`, `vp8_stcodec`, and
  `vp9_stcodec` decoding with CPU-readable I420 output.
- Firefox k3.9 handles independent V4L2 decode capability queries before the
  generic GLX failure return. Virtual Wayland therefore selects VP9 hardware
  decoding instead of FFVPX even when GLX and DMABUF are unavailable.
- No global hardware disablement, VP8/VP9 codec filtering, MPP log suppression,
  or silent substitution of software decoding for a hardware acceptance run.

Firefox k3.8 was rejected after its Wayland FFVPX failure and is not an asset
in this release. See `research/mpp-k38.md` and `research/firefox-wayland.md`.

## Validation

Native three-loop tests for each of H.264, HEVC, VP8, and VP9 produced exactly
1350 frames with continuous PTS `0..1349`, 450 identical hashes per epoch,
normal completion, and zero MPP errors.

The installed clean Firefox k3.9 deb passed strict local-file tests for all four
codecs under Xvfb, H.264 HTTP playback for 45 seconds across four flush epochs,
and VP9 under an isolated headless GNOME/Wayland virtual monitor. Every run
required the expected stcodec decoder, `IsHardwareAccelerated=1`, validated
per-epoch hardware PTS, measurable VPU interrupts, and zero MPP errors.

Final browser VPU interrupt deltas were 10389 (H.264), 11054 (HEVC), 7583 (VP8),
11167 (VP9), 29112 (HTTP H.264), and 11114 (Wayland VP9). AV1 was separately
verified as FFVPX/libdav1d software decoding with no `av1_stcodec` claim.

Xvfb/headless Wayland presentation drops are reported separately from decoder
frame completeness. The Wayland test is virtual-display evidence, not physical
monitor validation.

## Source-lintian disclosure

Firefox binary lintian has zero errors. Full source lintian reports four errors
in byte-identical files inherited from the upstream orig tar and temporary-index
warnings for one upstream gzip test file; no overrides were added and a clean
source-lintian result is not claimed. See `STATUS.md` and
`artifacts/validation/firefox-source-lintian-origin.json` for the raw scope.

## Installation notes

Install matching MPP, FFmpeg runtime, and Firefox packages together. Do not mix
this libavcodec with an older MPP. `/dev/video0` remains `root:video 0660`;
desktop users need membership in the `video` group.

Strict hardware validation uses:

```text
media.hardware-video-decoding.enabled=true
media.hardware-video-decoding.force-enabled=true
media.ffmpeg.disable-software-fallback=true
```

AV1 has no K3 stcodec and remains software-only; do not interpret its software
control as a supported hardware decoder.

The PPA target is `ppa:mymathersname-gmail/ppa`. Launchpad upload/build and
publication status is tracked separately in `STATUS.md`; a local build or dput
exit code alone is not a claim that a PPA binary is published.
