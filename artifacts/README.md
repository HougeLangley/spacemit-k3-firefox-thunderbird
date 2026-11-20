# Release assets and evidence

`SHA256SUMS` covers the eleven binary assets staged for the
`v160.0-k3.9-20261120` pre-release: Firefox k3.9, MPP k3.8, eight matching
FFmpeg k3.2 runtime/CLI packages, and the unchanged Thunderbird k3.1
compatibility package. Debug symbols, development packages, locale packages,
source archives, rejected candidates, and diagnostic objects are excluded.

`validation/` contains thirteen JSON manifests copied from the accepted local
runs or the source-lintian origin audit, plus the raw binary/source lintian
logs. The media validator was not modified:

- four native three-epoch codec results;
- four final Firefox Xvfb codec results;
- final Firefox HTTP 45-second and virtual-Wayland VP9 results;
- virtual compositor metadata and the AV1 software control;
- source-lintian upstream-origin hashes and raw binary/source lintian logs.
  Source lintian is **not** claimed to be clean; see `../STATUS.md` for the four
  inherited upstream errors and the temporary-index warnings.

The manifests are evidence exports, not remote publication proof. Their raw
logs remain on the build host under
`/mnt/k3work/firefox-k3/tests/mpp-hw/browser-k39-final/` and the corresponding
`long-samples/` directory. GitHub and Launchpad status must be fetched
independently from those services.
