# K3 Firefox / Thunderbird status — 2026-11-20

## Local candidate

The hardware-decoding candidate is MPP `0.1.15+k3.8`, FFmpeg
`7:8.0.1-3ubuntu2bb1k3.2`, and Firefox
`160.0+build1-0ubuntu0.26.04.1~mt1k3.9` for Ubuntu 26.04 `riscv64` on
SpacemiT K3. Firefox k3.8 was rejected after its virtual-Wayland FFVPX failure;
its artifacts and evidence are quarantined and are not release inputs.

Release tag: `v160.0-k3.9-20261120` at commit
`6e8548fe57e632b1277c8bc91fec9bcbf4db3145`.

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

## Remote publication

### GitHub — independently verified

- `main` and `v160.0-k3.9-20261120` resolve to commit
  `6e8548fe57e632b1277c8bc91fec9bcbf4db3145`.
- New pre-release:
  <https://github.com/HougeLangley/spacemit-k3-firefox-thunderbird/releases/tag/v160.0-k3.9-20261120>
- The release contains eleven binary assets plus `SHA256SUMS`. All twelve files
  were downloaded again from GitHub; all eleven checksums passed, and the
  downloaded Firefox deb's internal version was read back as k3.9.
- GitHub normalized `~` to `.` in the Firefox download filename. The attached
  remote `SHA256SUMS` uses the actual download names; the package version and
  SHA-256 are unchanged. The build-host/source-tag manifest retains the
  original Debian filename.

### Launchpad — uploaded, builds/publication still in progress

All three source uploads were signed with the newly registered key
`C4C81FA09FBEFA879F6E21A3444C383074940157`; Launchpad's API lists that
fingerprint for `~mymathersname-gmail`. Every `.dsc` and `.changes` signature
was verified locally before `dput`. FTP success is not treated as publication.

Latest independently fetched state at `2026-11-20T17:41:46Z`:

| Source | Upload/build evidence | Current state |
|---|---|---|
| MPP k3.8 | sourcepub `18971839`; build `33997821` | source Pending; riscv64 Needs building |
| FFmpeg k3.2 | sourcepub `18971840`; build `33997822` | source Pending; riscv64 Needs building |
| Firefox k3.9 | dput completed | new source/build record not yet visible at this read |

Build links:
<https://launchpad.net/~mymathersname-gmail/+archive/ubuntu/ppa/+build/33997821>
and
<https://launchpad.net/~mymathersname-gmail/+archive/ubuntu/ppa/+build/33997822>.
No new PPA binary is claimed to be Published. The Launchpad monitor continues
to query exact new versions and primary binary publications; old Firefox build
records are not evidence for this release.

## Security and scope

No token, private key, or passphrase is stored in this repository.
`/dev/video0` remains `root:video 0660`; no permissive device rule was added.
Hardware encoding restrictions and AV1 software-only behavior remain intact.
