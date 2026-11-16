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

## PPA monitor — retry attempt

- Old source: `160.0+build1-0ubuntu0.26.04.1~mt1k3.1`, build `33970093`; still `Currently building` after >39h, no log/datebuilt/binaries.
- Retry 1: `~mt1k3.2` (diff-only), build `33975072`; **Failed to build** after 4 minutes, no build log URL.
- Retry 2: `~mt1k3.3` (full orig source included), build **`33975178`**; **Currently building**, dispatched `2026-11-16T13:31:24Z`.
- The old stuck build was not cancelled. No published Firefox binaries yet.
- Recurring 2-hour monitor updated to check both `33975178` and `33970093`.

Build URLs:
- <https://launchpad.net/~mymathersname-gmail/+archive/ubuntu/ppa/+build/33975178>
- <https://launchpad.net/~mymathersname-gmail/+archive/ubuntu/ppa/+build/33970093>

## Security notes

- No GitHub token, private key, or passphrase value is stored in this repository.
- Internal onboarding/checkpoint notes were removed from the public tree.
- The GitHub token used for publishing was shared in chat and must be revoked by its owner.
