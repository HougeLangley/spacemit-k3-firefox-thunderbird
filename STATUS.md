# K3 Firefox / Thunderbird status — 2026-11-24

## Validated local candidate

The GitHub hardware-decoding candidate is MPP `0.1.15+k3.8`, FFmpeg
`7:8.0.1-3ubuntu2bb1k3.2`, and Firefox
`160.0+build1-0ubuntu0.26.04.1~mt1k3.9` for Ubuntu 26.04 `riscv64` on
SpacemiT K3. Firefox k3.8 was rejected after its virtual-Wayland FFVPX failure;
its artifacts and evidence are quarantined and are not release inputs.

Release tag: `v160.0-k3.9-20261120` at commit
`6e8548fe57e632b1277c8bc91fec9bcbf4db3145`. The `main` branch contains
subsequent documentation and PPA-remediation evidence; the release tag has not
been moved merely to update documentation.

| Product | Version | Primary SHA256 |
|---|---|---|
| Firefox | `160.0+build1-0ubuntu0.26.04.1~mt1k3.9` | `dce19bab115fd8168328d61163a7f09d4cdf0f30c3eda11778d8284b28a973a0` |
| MPP | `0.1.15+k3.8` | `8f71188822085d9209618621966ad39820d88a3c49b93e05537995440ea1df2b` |
| FFmpeg libavcodec | `7:8.0.1-3ubuntu2bb1k3.2` | `64bbb5dfaa0ce9ebc5bcce44ba0b6f3ac6b4a1266133504bd34473f256494471` |
| Thunderbird (unchanged) | `1:160.0-1k3.1` | `53460aae7f4454db32c176d75a76ae3358f76b8129df4529ec1c67271eb195cb` |

`artifacts/SHA256SUMS` covers the eleven staged assets. Thunderbird is an
unchanged compatibility asset, not a new build or a newly retested product.

## Accepted hardware evidence

Native three-loop H.264/HEVC/VP8/VP9 tests each produced exactly 1350 frames,
continuous PTS `0..1349`, 450 unique hashes per epoch, identical hashes across
epochs, normal completion, no timeout, and zero MPP errors.

The installed clean Firefox k3.9 deb passed:

| Scenario | Decoder | Hardware frame logs | VPU IRQ delta | MPP errors |
|---|---|---:|---:|---:|
| H.264 Xvfb | `h264_stcodec` | 516 | 10389 | 0 |
| HEVC Xvfb | `hevc_stcodec` | 515 | 11054 | 0 |
| VP8 Xvfb | `vp8_stcodec` | 519 | 7583 | 0 |
| VP9 Xvfb | `vp9_stcodec` | 522 | 11167 | 0 |
| H.264 HTTP 45 s | `h264_stcodec` | 1417 | 29112 | 0 |
| VP9 virtual GNOME/Wayland | `vp9_stcodec` | 525 | 11114 | 0 |

All require strict hardware preferences, `IsHardwareAccelerated=1`, 450
validated hardware PTS per epoch, no later software decoder, and positive VPU
interrupt activity. The HTTP run covers four process flushes. AV1 separately
passed a software control using FFVPX/libdav1d, with no `av1_stcodec` and zero
MPP errors.

The Wayland run used a headless virtual monitor, not a physical display.
Presentation drops under Xvfb/software WebRender are not relabeled as decoder
loss. Evidence exports are in `artifacts/validation/`.

## Build and package gates

- MPP k3.8: final binary build, binary/source lintian error gates, and an
  independent `.dsc` extraction followed by binary roundtrip rebuild passed.
- FFmpeg k3.2: the same binary/source and independent binary roundtrip gates
  passed. Its runtime dependency requires MPP k3.8 or newer.
- Firefox k3.9: authoritative-tree clean binary build and full binary lintian
  error gate passed; the installed package versions and dependency floors were
  read back with `dpkg-query` and `dpkg-deb`.
- Firefox source package was generated. Independent `.dsc` extraction and a
  recursive diff found only the generated `debian/files` metadata file;
  source, control, patches, GfxInfo, and FFmpeg decoder sources are identical.
  This is a source extraction/diff roundtrip, not a claim of a second Firefox
  binary rebuild.

### Firefox source lintian is not clean

`lintian --fail-on error` completed with four errors in unchanged files from
the upstream `orig.tar.xz`:

- two `binary-with-bad-dynamic-table` tags in dump_syms test data;
- `license-problem-convert-utf-code` in the upstream Breakpad source;
- `license-problem-md5sum-non-free-file` for the upstream W3C HTML icon.

No lintian override was added and these errors are not described as fixed.
`artifacts/validation/firefox-source-lintian-origin.json` records their
orig-tar hashes and byte identity with the working tree. No new K3-delta error
was reported. Lintian also emitted temporary-index warnings for
`devtools/client/styleeditor/test/simple.css.gz` and skipped five checks even
though the file exists in both the working tree and roundtrip extraction. The
raw log is preserved in `artifacts/validation/firefox-source-lintian.log`.
Accordingly, a zero-error full source-lintian result is **not** claimed.

## PPA dependency remediation — MPP k3.9

The first attempt of Launchpad's FFmpeg k3.2 build `33997822` failed during
`install-deps`, before compilation. Its failure log reported that MPP's hard
dependency `k1x-vpu-firmware | k3x-vpu-firmware` was not installable in the
build chroot, which at that time had no firmware provider.
The real `k3x-vpu-firmware` package used on K3 comes from the official
`ppa:spacemit/k3` archive; no dummy firmware package was created.

MPP `0.1.15+k3.9` moves that runtime alternative from `Depends` to `Recommends`.
Normal apt installation still selects the real firmware by default, while a
build chroot using `--no-install-recommends` can resolve MPP development files
without runtime firmware in its archive. Decoder source and Firefox's strict
hardware preferences are unchanged.

Independent source extraction found exactly two k3.8-to-k3.9 differences:
`debian/control` and `debian/changelog`. Binary and source lintian exited zero.
An empty-dpkg-status apt simulation selected no firmware with recommends
disabled and selected `k3x-vpu-firmware` with normal recommends enabled. A
rebuilt ELF is not claimed to be byte-identical to the k3.8 build.

The installed MPP k3.9 package retained firmware `4.5.0.20241231-1bb1` and
passed a new four-codec regression:

| Codec | Frames | PTS | Unique hashes per epoch | Epoch hashes | VPU IRQ delta | MPP errors |
|---|---:|---|---|---|---:|---:|
| H.264 | 1350 | `0..1349` | 450 / 450 / 450 | identical | 17936 | 0 |
| HEVC | 1350 | `0..1349` | 450 / 450 / 450 | identical | 17774 | 0 |
| VP8 | 1350 | `0..1349` | 450 / 450 / 450 | identical | 17740 | 0 |
| VP9 | 1350 | `0..1349` | 450 / 450 / 450 | identical | 17822 | 0 |

The reproducible packaging patch is
`patches/k3-mpp-ppa-firmware-recommends.patch`. Evidence is recorded in
`artifacts/validation/mpp-k39-packaging-validation.json`,
`mpp-k39-native-validation.json`, and `mpp-k39-signature-verification.json`.
The GitHub k3.8 binary remains the validated release asset; it is not relabeled
as the PPA-only k3.9 packaging revision.

### What made the retried FFmpeg k3.2 build succeed

The official log of the successful retry of build `33997822` shows two facts
that an earlier revision of this page recorded incorrectly:

- The retry ran from `2026-11-23T10:10:41Z` to `2026-11-23T16:44:09Z`
  (`Status: successful`, 6 h 13 min 32 s). Its chroot used an archive
  dependency on `ppa:spacemit/k3` (apt pin `LP-PPA-spacemit-k3:500`); the
  Launchpad API now reports one archive dependency.
- The chroot installed MPP `0.1.15+k3.8` together with the real
  `k3x-vpu-firmware 4.5.0.20241231-1bb1`. The build passed `install-deps`
  through the real firmware provider, not through MPP k3.9, whose binary was
  published only at `13:11:02Z`.

Correction: the state recorded at `2026-11-23T12:24Z` said that the build had
not been retried and that archive dependencies were empty. The official build
log contradicts both statements; they are withdrawn. No dummy firmware was
involved in either path.

Line-referenced excerpts are in
`artifacts/validation/ffmpeg-k32-launchpad-build-analysis.json`. MPP k3.9
remains published and independently removes the hard build-time firmware
requirement, so later builds resolve even without the external archive.

## Remote publication

### GitHub — independently verified

- `v160.0-k3.9-20261120` resolves to commit
  `6e8548fe57e632b1277c8bc91fec9bcbf4db3145`.
- Pre-release:
  <https://github.com/HougeLangley/spacemit-k3-firefox-thunderbird/releases/tag/v160.0-k3.9-20261120>
- The release contains eleven binary assets plus `SHA256SUMS`. All twelve files
  were downloaded again from GitHub; all eleven checksums passed, and the
  downloaded Firefox deb's internal version was read back as k3.9.
- GitHub normalized `~` to `.` in the Firefox download filename. The attached
  remote `SHA256SUMS` uses the actual download names; the package version and
  SHA-256 are unchanged. The build-host/source-tag manifest retains the
  original Debian filename.

### Launchpad — MPP and FFmpeg published; Firefox still building

Source uploads were signed with the newly registered key
`C4C81FA09FBEFA879F6E21A3444C383074940157`; Launchpad's API lists that
fingerprint for `~mymathersname-gmail`. Every new MPP `.dsc`, `.buildinfo`, and
`.changes` signature was verified locally before `dput`. FTP success is not
treated as publication.

Latest independently fetched state at `2026-11-24T13:15Z`:

| Source | Source/build evidence | Current state |
|---|---|---|
| MPP k3.8 | sourcepub `18971839`; build `33997821` | superseded by k3.9; no longer in the live riscv64 index |
| MPP k3.9 | sourcepub `18975916`; build `34004509`; binarypub `254124874` | source and riscv64 binary Published (binary at `2026-11-23T13:11:02Z`) |
| FFmpeg k3.2 | sourcepub `18971840`; build `33997822` | source Published; riscv64 build Successfully built; all 22 riscv64 binaries Published (`2026-11-23T17:19:54Z`) and listed in the live index |
| Firefox k3.9 | sourcepub `18971844`; build `33997839` | source Published; riscv64 Currently building on `bos03-riscv64-018` since `2026-11-22T16:34:31Z`; no binary publication |

Build links:
<https://launchpad.net/~mymathersname-gmail/+archive/ubuntu/ppa/+build/33997821>,
<https://launchpad.net/~mymathersname-gmail/+archive/ubuntu/ppa/+build/34004509>,
<https://launchpad.net/~mymathersname-gmail/+archive/ubuntu/ppa/+build/33997822>,
and
<https://launchpad.net/~mymathersname-gmail/+archive/ubuntu/ppa/+build/33997839>.

A direct read of the live riscv64 `Packages.gz` at `2026-11-24T13:15Z` lists
MPP k3.9 with firmware in `Recommends` and no hard firmware dependency in
`Depends`, plus all 22 FFmpeg k3.2 riscv64 packages. `ffmpeg-doc`
(architecture `all`) is also published for the archive's other architectures;
no non-riscv64 FFmpeg library is claimed. No Firefox PPA binary is published.
Firefox build `33997839` remains an active build record; obsolete Firefox
build records are not evidence for this release.

### PPA-published FFmpeg binaries pass the hardware regression

On `2026-11-24` the published riscv64 `.deb` files were downloaded from the
PPA pool, each verified against the SHA-256 in the live `Packages.gz`,
unpacked without installing, and run directly on the K3. `/usr/bin/ffmpeg`
came from the published package and all eight project libraries resolved to
the unpacked files. The installed MPP payload was compared with the published
MPP k3.9 package: 20 of 20 `/usr/lib` entries (17 files and symlinks,
including `libv4l2_linlonv5v7_codec.so`) are byte-identical.

| Codec | Frames | PTS | Unique hashes per epoch | Epoch hashes | VPU IRQ delta | MPP errors |
|---|---:|---|---|---|---:|---:|
| H.264 | 1350 | `0..1349` | 450 / 450 / 450 | identical | 18750 | 0 |
| HEVC | 1350 | `0..1349` | 450 / 450 / 450 | identical | 19107 | 0 |
| VP8 | 1350 | `0..1349` | 450 / 450 / 450 | identical | 18398 | 0 |
| VP9 | 1350 | `0..1349` | 450 / 450 / 450 | identical | 20505 | 0 |

Every decoded frame hash equals the earlier locally built validation, so the
published library decodes the same frames as the validated candidate. The
Launchpad-built packages are not all byte-identical to the local build (15 of
22 match; the runtime libraries `libavcodec62`, `libavutil60`, `libswscale9`,
and `libavfilter11` differ), which is why the published files were tested
separately. Evidence: `ffmpeg-k32-ppa-published-hardware-validation.json`,
`ffmpeg-k32-ppa-deb-identity.json`, `mpp-k39-ppa-payload-identity.json`, and
`ffmpeg-k32-ppa-publication-state.json` in `artifacts/validation/`.

FFmpeg k3.3 (only the MPP floor raised to k3.9) was built and validated
locally but deliberately not uploaded: it would supersede a Published,
validated k3.2 with no functional change. Its record is
`ffmpeg-k33-local-only-validation.json`.

## Security and scope

No token, private key, or passphrase is stored in this repository.
`/dev/video0` remains `root:video 0660`; no permissive device rule was added.
Hardware encoding restrictions and AV1 software-only behavior remain intact.
