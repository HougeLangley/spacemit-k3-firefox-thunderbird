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

## Delivery record #2 — 2026-11-18T11:00Z (no rating)

- PUA visible: `[PUA-DIAGNOSIS]` and the delivery summary for the YouTube/MPP fix.
- Local artifact: Firefox `160.0+build1-0ubuntu0.26.04.1~mt1k3.6` installed;
  `/etc/firefox/syspref.js` disables `media.hardware-video-decoding.enabled`.
- PPA 1.5 `33984218`: `Needs building`; old `33976658` 37.78h and `33970093`
  85.24h remain `Currently building`; published Firefox binaries: 0.
- Rating: intentionally not recorded.

## Delivery record #3 — 2026-11-18T14:25Z (no rating)

- PUA visible: JIT/codec diagnosis, L0-L3 experiment tracking, `[PUA 突破 ✨]`
  after the controlled JIT A/B measurement succeeded, and the final no-publish
  decision. No score was recorded.
- Decision: **no JIT source/default change, no new local deb, and no new PPA
  upload**. The installed Firefox remains local 1.6 with the hardware-decode
  fallback; there is no evidence that changing `js/src/jit/riscv64` fixes this
  YouTube symptom.
- Controlled JIT A/B (same 240p video, default thresholds `10/100/1500`):
  R0 default JIT completed 31 samples with max event-loop lag 0 s and 0 dropped
  frames. R3 (`blinterp=true`, `baselinejit=true`, `ion=false`) also completed
  31 samples, with max lag 3.2 s and 2 dropped frames; disabling Ion/Warp did
  not demonstrate a benefit.
- High-load default-JIT AV1: itag 399 (1080p60) had 2055/2345 dropped frames
  before player reset; itag 398 (720p60) had 2445/3126 dropped frames in the
  measured interval. Main-thread sample lag stayed at 0-0.1 s, so these runs
  do not support a JS/JIT main-thread diagnosis.
- Codec A/B: disabling AV1 selected VP9 itag 303 and still produced 2652/3176
  dropped frames. Forcing H.264 selected itag 299 and avoided the same player
  reset, but network `ratelimited` buffering starvation dominated its 60 s run;
  this is not sufficient evidence for a global codec-pref release.
- AV1 thread strategy: `media.av1.new-thread-count-strategy=true` changed 480p
  dropped-frame ratio only from 56.5% to 55.0%; not a release-worthy fix.
- Measurement harness and raw results: `../tests/youtube-jit/`; Marionette was
  used after BiDi navigation/viewport callbacks proved unreliable.
- Environment limits: Xvfb uses software WebRender, whose source gate prevents
  V4L2 hardware decode, so these runs do not validate the friend's real MPP
  hardware path. The DSH process affinity is CPUs 0-7; an attempt to run the
  isolated browser on CPUs 0-15 was rejected. YouTube also reported
  `ratelimited` in several runs. Real graphical-session/friend confirmation is
  still required before publishing another workaround.
- PPA monitor at this delivery: 1.5 build `33984218` remains `Needs building`;
  `33976658` and `33970093` remain `Currently building` (41.05 h and 88.51 h);
  published Firefox binaries: 0. No old build was cancelled or retransmitted.
- Rating: intentionally not recorded.

## Delivery record #4 — 2026-11-18T14:31Z (no rating)

- PUA visible: `只记录可见 PUA、构建事实和验证证据，不记录评分` and the
  `[PUA-DIAGNOSIS]` line binding the Launchpad status query, atomic status
  update, independent reread, duplicate check, and reviewable Git diff.
- Delivery carried forward: YouTube JIT/codec investigation is recorded in local
  commit `8acf168`; no JIT source/default change, no new deb, and no new PPA
  upload was made because no tested workaround met the playback acceptance.
- PPA check at `2026-11-18T14:31:32Z`: Firefox 1.5 build `33984218` remains
  `Needs building` (no start time, binary, or build log). Old build `33976658`
  remains `Currently building` at 41.30 h; old build `33970093` remains
  `Currently building` at 88.76 h. Published Firefox binaries: 0.
- No build was cancelled, retried, or retransmitted; no token was printed.
- Rating: intentionally not recorded.
