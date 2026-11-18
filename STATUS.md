# K3 Firefox / Thunderbird Status — 2026-11-16T12:53Z

## Delivered artifacts

| Product | Version | Deb | SHA256 |
|---|---|---|---|
| Firefox | 160.0 | `firefox_160.0+build1-0ubuntu0.26.04.1~mt1k3.1_riscv64.deb` | `e3db74a79f515d41170d901494140b63200cadd55b9ea609d4ff1774fc917610` |
| Thunderbird | 160.0 | `thunderbird_160.0-1k3.1_riscv64.deb` | `53460aae7f4454db32c176d75a76ae3358f76b8129df4529ec1c67271eb195cb` |

GitHub release:
<https://github.com/HougeLangley/spacemit-k3-firefox-thunderbird/releases/tag/v160.0-k3-20261116>

Installed smoke test:

```text
Mozilla Firefox 160.0
Mozilla Thunderbird 160.0
thunderbird 1:160.0-1k3.1 riscv64
```

## Compiler verification

- Firefox `config.status`: `CC_TYPE=clang`, `CC_VERSION=24.0.0`.
- Thunderbird `config.status`: `CC`, `CXX`, `HOST_CC` all point to clang/clang++ 24; `CC_TYPE=clang`.
- Thunderbird build log: 267 clang++ command lines; `0` gcc/g++ command lines.
- `GCC_USE_GNU_LD=1` is only a configure marker for GNU-ld option naming, not a compiler choice.

Latest clang available in this environment: `24.0.0git` (system's highest is clang-22).

## RVV / IME scan

Firefox `libxul.so`:

```text
vmadot=0  vfwmadot=0  vsetvli=79044  vle=70516  vse=127970  vwmacc=1076
```

Thunderbird 160 `libxul.so`:

```text
vmadot=0  vfwmadot=0  vsetvli=76883  vle=64979  vse=118348  vwmacc=1058
```

Interpretation:

- RVV auto-vectorization is present and substantial.
- IME1 (`vmadot`) and IME2 (`vfwmadot`) instruction counts are **zero**.
- `-march=...xsmtvdot_xsmtvdotii` only gives the compiler the ability to emit IME; the browser sources have no IME kernels, so no IME acceleration is actually used.
- Real IME acceleration requires hand-written/integrated kernels; IME2 is A100-cluster-only on K3.

## YouTube MPP error fix — 2026-11-18

Root cause: `libv4l2_linlonv5v7_codec.so` on K3 only implements H.264/HEVC,
but Firefox maps VP8/VP9/AV1 to `vp8_v4l2m2m`/`vp9_v4l2m2m`/`av1_v4l2m2m`.
YouTube's VP9/AV1 frames therefore hit the MPP decoder and produce
`[MPP-ERROR] ... handleOutputBuffer ... error frame`.

Fix:
- `patches/k3-v4l2-codec-filter.patch`: in `FFmpegVideoDecoder.cpp`,
  disable VP8/VP9/AV1 V4L2 M2M selection on RISC-V; H.264/HEVC keep hardware
  decode, VP9/AV1 fall back to software.
- Local `~mt1k3.6` deb also disables `media.hardware-video-decoding.enabled`
  in `/etc/firefox/syspref.js` as a safe fallback, so the currently installed
  binary cannot enter the MPP path.

Verification:
- Rebuilt `Unified_cpp_ffmpeg_ffmpeg*.o`: `vp8/vp9/av1_v4l2m2m` strings are
  gone, `h264/hevc_v4l2m2m` remain.
- Local 1.6 installed; `firefox --version` = 160.0; syspref present.

## PPA monitor

- 1.4 `33976658`: still `Currently building`, no binary.
- 1.5 `33984218` (source patch): **`Needs building`**.
- Old 1.1 `33970093`: still `Currently building`.
- No published Firefox binaries yet.

Build URLs:
- <https://launchpad.net/~mymathersname-gmail/+archive/ubuntu/ppa/+build/33984218>
- <https://launchpad.net/~mymathersname-gmail/+archive/ubuntu/ppa/+build/33976658>
- <https://launchpad.net/~mymathersname-gmail/+archive/ubuntu/ppa/+build/33970093>

## Security notes

- No GitHub token, private key, or passphrase value is stored in this repository.
- Internal onboarding/checkpoint notes were removed from the public tree.
- The GitHub token used for publishing was shared in chat and must be revoked by its owner.

## Delivery record — 2026-11-18 (no rating)

- PUA visible output: `[PUA-DIAGNOSIS]` for the YouTube/MPP path, followed by the
  final delivery note.
- Root cause: K3 `libv4l2_linlonv5v7_codec.so` only handles H.264/HEVC, while
  Firefox routed VP8/VP9/AV1 to `*_v4l2m2m`; YouTube VP9/AV1 produced MPP error
  frames.
- Fix: `k3-v4l2-codec-filter.patch` disables VP8/VP9/AV1 V4L2 on RISC-V and
  keeps H.264/HEVC; local 1.6 additionally disables
  `media.hardware-video-decoding.enabled` as a fallback.
- Evidence: rebuilt FFmpeg unified objects show `vp8/vp9/av1_v4l2m2m` removed
  and `h264/hevc_v4l2m2m` retained; local Firefox 1.6 installed; GitHub release
  asset `firefox_160.0+build1-0ubuntu0.26.04.1~mt1k3.6_riscv64.deb`.
- PPA: 1.5 build `33984218` is `Needs building`; old builds `33976658` and
  `33970093` remain `Currently building`; no published Firefox binaries.
- Rating: intentionally not recorded.
