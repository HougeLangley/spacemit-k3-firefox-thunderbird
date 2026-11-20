# Firefox K3 Wayland: GLX failure must not hide an independent VPU

Date: 2026-11-20 (UTC)

## Rejected k3.8 behavior

The k3.8 package passed local-file and HTTP hardware-decoding tests under
Xvfb, but the isolated GNOME/Wayland VP9 test selected FFVPX instead of
`vp9_stcodec`. `about:support` showed `FEATURE_FAILURE_GLXTEST_FAILED` for
`HARDWARE_VIDEO_DECODING` and `VP9_HW_DECODE`.

The source-level cause was control flow, not an MPP playback failure:
`GfxInfo::GetFeatureStatusImpl()` returned early for `mGlxTestError` before the
RISC-V V4L2 probe. A probe placed later in that function cannot repair this
path. Per-codec queries also returned before reaching the codec capability
bitmap.

All k3.8 package artifacts and browser evidence were retained under the
separate `rejected/firefox-k38-wayland-glxtest` and `browser-k38-rejected`
paths. They are not release candidates.

## k3.9 fix

On RISC-V, when hardware video decoding is enabled, Firefox now handles these
queries before the generic GLX failure return:

- `FEATURE_HARDWARE_VIDEO_DECODING`;
- H.264, HEVC, VP8, VP9, and AV1 hardware-decode feature queries.

The handler runs the existing V4L2 device probe and returns status from the
actual global/per-codec capability result. AV1 is not enabled by assumption:
if the probe has no AV1 capability bit, the feature remains blocked. Hardware
encoding queries deliberately retain their previous GLX and DMABUF gates.
This change does not disable software WebRender, hide GPU failures, or permit
a later software decoder during a strict hardware test.

## Diagnostic evidence

A diagnostic obj build linked the updated `libxul.so`. Its later newtab
webpack step failed with a WebAssembly allocation error, so that obj build is
explicitly not a release artifact. The already-linked browser was sufficient
for an isolated media-path test.

The virtual GNOME/Mutter session used a 1280x720 headless monitor and
`/dev/dri/renderD128`; it did not use Xvfb or Xwayland. Strict VP9 validation
produced:

| Signal | Result |
|---|---:|
| Decoder | `vp9_stcodec` |
| `IsHardwareAccelerated` log | 1 |
| Hardware frame logs | 529 |
| Validated hardware PTS per epoch | 450 |
| Process flushes | 2 |
| VPU interrupt delta | 11051 |
| MPP errors / error frames | 0 / 0 |
| Window backend | Wayland |

`about:support` independently reported global hardware decoding and VP9 as
available. AV1 remained blocked with `FEATURE_FAILURE_VIDEO_DECODING_MISSING`;
hardware encoding remained blocked by the existing GLX/DMABUF requirements.

The virtual software-compositor run reported 21 presentation dropped frames.
That is not concealed or relabeled as decoder frame loss. Decoder completeness
is tested separately by native three-epoch framehash runs requiring exactly
1350 frames, continuous PTS, and identical per-epoch hashes.

Evidence:
`/mnt/k3work/firefox-k3/tests/mpp-hw/browser-k39-diagnostic/vp9-15s-wayland-gnome/`.

These are virtual-display diagnostic results, not physical-desktop validation
and not proof of final package publication. The final Firefox k3.9 package
must pass its own clean-build, installation, Xvfb, HTTP, and Wayland tests.
