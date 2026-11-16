# Firefox/Thunderbird K3 packaging — checkpoint

Updated: 2026-11-14 13:40 +08:00

## Goal
- Firefox 160 + Thunderbird 140.17 `.deb` for Ubuntu 26.04 riscv64 (K3).
- Local build: clang-24 (LLVM 24, RVV+IME1+IME2 target), Rust 1.100 (rustup, riscv64gc), `-O3 -march=rv64gcv_zba_zfh_zvfh_zicbop_xsmtvdot_xsmtvdotii -mtune=spacemit-a100`.
- PPA `firefox-k3` (user `mymathersname-gmail`), Phase 1 clang-22 + rustc-1.91 + RVV/IME1.

## Verified
- Host: 8×X100 (0-7, VLEN=256, 2.15GHz) + 8×A100 (8-15, VLEN=1024, 1.8GHz); shell affinity 0-7; `ai-run` gives A100/VLEN=128/IME2_OK.
- IME1 `vmadot` works on both clusters; IME2 `vfwmadot` A100-only.
- clang-24 supports xsmtvdot + xsmtvdotii; Rust 1.100 supports both target features; Rust 1.97 only IME1; Rust 1.91 host=riscv64gc (last archive version with gc; 1.92+ a23), no IME features.
- Firefox local tree: /mnt/k3work/firefox-k3/build/firefox-160.0; configure complete (clang-24, lld-24 wrapper, Rust 1.100, libclang-22 for bindgen); `mach build` running (started 12:48, ~50min, dom/file stage, 1378 .o).
- Ubuntu 26.04 `cdbs` lacks `/usr/share/cdbs/1/class/makefile.mk`; patched `debian/build/rules.mk` in FF/TB with explicit `stamp-makefile-build -> mach build` and `stamp-makefile-install`; this is required for PPA too.
- PPA Phase 1 source package built and signed:
  - `/mnt/k3work/firefox-k3/ppa/firefox_160.0+build1-0ubuntu0.26.04.1~mt1k3.1_source.changes`
  - includes 790MB orig tar, signed `.dsc`, checksums verified, `dput -s` valid.
  - `dpkg-source -x` + 13 patches + `dpkg-checkbuilddeps` pass in `/mnt/k3work/firefox-k3/ppa-verify/firefox-160.0`.
- GPG key: `2F96685F99925C8797DD521B308DCCA0A8D0D841` (`Yeqin Su <hougelangley1987@gmail.com>`), public key at `ppa-keys/ppa-signing-key.asc`, published to keyserver.ubuntu.com; passphrase at `ppa-keys/passphrase` (600).
- PPA onboarding: `PPA-ONBOARD.md`; Launchpad currently still shows 0 gpg_keys/0 ppas (user action pending).
- Thunderbird source tree: `/mnt/k3work/firefox-k3/build/thunderbird-140.17.0`; Python 3.14 AST patch applied to `python/mach/mach/command_util.py`; switched to real `rustc-1.91` (host gc), clang-24, IME1; configure4 running.

## Failed attempts / fixed
1. Debian orig tar missing cbindgen -> Ubuntu tar.
2. Missing mozconfig -> clang-21/no rustc.
3. Ubuntu rustc-1.97/1.93 host a23 -> rustup 1.97.1/1.100 host gc.
4. clang-24 no libclang -> `--with-libclang-path=/usr/lib/llvm-22/lib`.
5. `dpkg-buildpackage` skipped mach build due to missing cdbs class -> explicit stamps.
6. TB Python 3.14 `ast.Str.s` -> `ast.Constant.value`.
7. TB rustup wrapper -> `rustc which rustc`; switched to real rustc-1.91.

## Next
- Wait for FF `mach build` to finish; run `dpkg-buildpackage -b -us -uc -d -nc -j8`; install/smoke test; scan libxul for IME/RVV; benchmark.
- Wait for TB configure4; if green, build TB on A100 (`ai-run make -f debian/rules debian/stamp-makefile-build`, -j6), then binary.
- PPA: user must register GPG key / create PPA / enable riscv64; then `dput` the signed `.changes`. Monitor API.
- Phase 2: minimal clang-24 PPA package if IME2 required in archive.

## Key paths
- FF source/build: `/mnt/k3work/firefox-k3/build/firefox-160.0`
- TB source/build: `/mnt/k3work/firefox-k3/build/thunderbird-140.17.0`
- PPA source/signed: `/mnt/k3work/firefox-k3/ppa/`
- Toolchain wrappers: `/mnt/k3work/firefox-k3/toolchain/bin`
- Logs: `/mnt/k3work/firefox-k3/logs`
- Research: `research/ime.md`, `research/toolchain.md`, `research/ppa.md`
- Checkpoint: this file
