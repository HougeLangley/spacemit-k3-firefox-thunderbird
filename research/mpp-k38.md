# SpacemiT K3 Linlon MPP k3.8: capture ownership and EOS

Date: 2026-11-19 (UTC)

This document records the MPP-side fixes and native decoder evidence. It does
not claim that the Firefox package, GitHub pre-release, or PPA upload has been
published.

## Hardware and decoder path

- VPU: `c0500000.linlon-v5`, exposed through `/dev/video0` and V4L2 M2M.
- System FFmpeg decoders: `h264_stcodec`, `hevc_stcodec`, `vp8_stcodec`, and
  `vp9_stcodec`.
- AV1 has no corresponding K3 hardware decoder and remains a separate
  software-decoding control case.
- Tests run as `ubuntu:video`; `/dev/video0` permissions are not relaxed.

## Root causes fixed

1. Color-description and EOS notifications were treated as decoder failures.
2. Output EOS was not latched at capture `V4L2_BUF_FLAG_LAST`, allowing an EOS
   error storm.
3. Request, return, flush, and reset could race while requeueing capture
   buffers.
4. Initialization and resolution changes require zero-length buffers to be
   returned to the driver, while a genuinely stale post-flush return must not
   be queued twice.
5. `handleOutputBuffer()` dequeues buffers for `MPP_CODER_NULL_DATA` and
   `MPP_ERROR_FRAME`, not only `MPP_OK`. k3.7 failed to transfer ownership for
   those cases. A second zero-length HEVC dequeue was therefore misclassified
   as an already queued stale buffer, no QBUF followed, and initialization
   timed out.

k3.8 marks every OK, NULL_DATA, or ERROR_FRAME capture dequeue as owned by the
caller and requiring a return. Genuine NO_DATA and the final EOS buffer do not
transfer ownership.

## Ownership transitions

| Event | `bIsBufferInDecoder[index]` | `bBufferNeedsReturn[index]` | Return behavior |
|---|---:|---:|---|
| After codec/stream setup or resolution reallocation | true | true | Initial registration QBUF is allowed |
| OK, NULL_DATA, or ERROR_FRAME DQBUF | false | true | Caller must return the buffer |
| Successful QBUF | true | false | Buffer is driver-owned |
| Flush/reset requeue | true | false | A later stale return is ignored |
| Capture LAST / latched EOS | true | false | Do not requeue after EOS |

The transitions are serialized by `outputMutex`. This does not suppress real
error logs or disable any codec.

## Native k3.8 evidence

All successful runs below used framehash output, strict PTS checks, and a
process-group timeout. Valid-playback logs contain zero `MPP-ERROR` lines.

| Test | Result | Evidence |
|---|---|---|
| VP8, 15 s | 450 frames, 450 unique PTS, 450 unique frame hashes, exit 0 | `vp8-stcodec-k38-validation.json` |
| VP9, 15 s | 450 frames, 450 unique PTS, 450 unique frame hashes, exit 0 | `vp9-stcodec-k38-validation.json` |
| HEVC, 15 s | 450 frames, 450 unique PTS, 450 unique frame hashes, exit 0 | `hevc-stcodec-k38-validation.json` |
| H.264, three loops with unmodified stcodec | Zero MPP errors, normal exit; 1330 frames because old stcodec drops ten valid frames after each later flush | `h264-loop3-k38-mpp-regression.json` |
| VP9 without `video` group | Decoder initialization fails cleanly with `-400`; no signal crash or timeout | `vp9-no-permission-k38.json` |

The 1330-frame H.264 run is intentionally **not** final frame-completeness
acceptance. After installing the diagnostic stcodec k3.1 build with MPP k3.8,
H.264, HEVC, VP8 and VP9 each produced 1350 frames over three loops, with PTS
exactly 0 through 1349 and identical per-epoch frame-hash sequences. Their
`*-loop3-k38-ffmpeg-k31-validation.json` files contain the individual results.
The final k3.2 package was then clean-built, installed, and subjected to the
same four-codec three-epoch test. All four final-package results passed with
1350 frames, PTS 0 through 1349, identical hashes across epochs, and zero MPP
errors; see `*-loop3-k38-ffmpeg-k32-validation.json`.

Evidence directory:
`/mnt/k3work/firefox-k3/tests/mpp-hw/long-samples/`.

## Source package verification

- MPP package: `mpp 0.1.15+k3.8`.
- MPP local binary build and `lintian --fail-on error`: passed.
- MPP independent `dpkg-source -x` roundtrip, binary rebuild, and lintian: passed.
- MPP roundtrip directory: `/mnt/k3work/mpp-roundtrip-k38/`.
- FFmpeg package: `ffmpeg 7:8.0.1-3ubuntu2bb1k3.2`; its local binary/source
  lintian gates and independent source-roundtrip binary rebuild also passed.
- FFmpeg roundtrip directory:
  `/mnt/k3work/ffmpeg-stcodec-source/roundtrip-k32/`.
- Public integration patch: `patches/k3-mpp-event-handling.patch`, generated against
  pristine `mpp 0.1.15`; `patch --dry-run -p1` passed for all three changed
  source files.

Final Firefox and FFmpeg packages must require MPP k3.8 or later. The older
k3.2 through k3.7 packages are diagnostic history, not release candidates.
