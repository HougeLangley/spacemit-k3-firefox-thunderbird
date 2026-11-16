# K3 Firefox / Thunderbird 构建交付报告

日期：2026-11-16（UTC）

GitHub 项目：https://github.com/HougeLangley/spacemit-k3-firefox-thunderbird
主机：Ubuntu 26.04 riscv64，SpacemiT K3（8×X100 + 8×A100，16 核异构）

## 1. 已交付：Firefox 160 deb（可用）

| 项 | 值 |
|---|---|
| deb | `/mnt/k3work/firefox-k3/artifacts/firefox_160.0+build1-0ubuntu0.26.04.1~mt1k3.1_riscv64.deb` |
| 大小 | 83 MB（Installed-Size 280710 KB，`libxul.so` 165 MB） |
| sha256 | `e3db74a79f515d41170d901494140b63200cadd55b9ea609d4ff1774fc917610` |
| 版本 | `160.0+build1-0ubuntu0.26.04.1~mt1k3.1` |
| 安装 | 已在本机 `apt-get install ./...deb` 成功；`firefox --version` → `Mozilla Firefox 160.0` |
| 截图 | `/mnt/k3work/firefox-k3/artifacts/firefox-k3-headless.png`（1280×1024，headless 3.38s） |
| lintian | 0 error；2 warning（revision 格式 `~mt1k3.1`、继承的 `Xul-Appid` 字段） |

### 构建参数
- C/C++：clang 24.0.0git（LLVM 24，含 `xsmtvdot` + `xsmtvdotii`）
- Rust：rustup 1.100.0（host `riscv64gc-unknown-linux-gnu`，LLVM 23）
- C++ flags：`-O3 -march=rv64gcv_zba_zfh_zvfh_zicbop_xsmtvdot_xsmtvdotii -mtune=spacemit-a100`
- Rust flags：`-C target-feature=+xsmtvdot`（IME1；不全局开 IME2，避免 X100 SIGILL）
- 链接：lld-22 转发；libclang-22 供 bindgen
- 构建耗时：`mach build` 172m07s（8×X100，约 1239 min CPU）；打包 40m15s

### 验收证据
- `firefox --version` → `Mozilla Firefox 160.0`
- headless：`--headless --screenshot` 成功，wall 3.38s，PNG 870 KB，渲染正常
- `libxul.so` 指令统计：
  - `vsetvli=79044`、`vle=70516`、`vse=127970`、`vwmacc=1076` → **RVV 实际大量使用**
  - `vmadot=0`、`vfwmadot=0` → **当前 Firefox 代码没有 IME 内核，未实际执行 IME1/IME2**
- 结论：`-march` 让编译器具备 IME 能力，但 Firefox/Skia/JPEG 等没有 IME 内核；IME 性能必须靠手写 kernel 或上游补丁，不能靠编译参数声称。详见 `research/ime.md`。

## 2. PPA：源码已发布，riscv64 build 长时间未结束

| 项 | 值 |
|---|---|
| PPA | `ppa:mymathersname-gmail/ppa`（display name：`firefox-k3`） |
| PPA URL | https://launchpad.net/~mymathersname-gmail/+archive/ubuntu/ppa |
| build record (old) | https://launchpad.net/~mymathersname-gmail/+archive/ubuntu/ppa/+build/33970093 |
| retry 1 (`~mt1k3.2`) | https://launchpad.net/~mymathersname-gmail/+archive/ubuntu/ppa/+build/33975072 — `Failed to build` |
| retry 2 (`~mt1k3.3`, full orig) | https://launchpad.net/~mymathersname-gmail/+archive/ubuntu/ppa/+build/33975178 — `Currently building` |
| 源码版本 | `160.0+build1-0ubuntu0.26.04.1~mt1k3.1` |
| source 状态 | `Published`（源码已发布） |
| riscv64 build | 旧 `33970093` 已 >39h；1.2 `33975072` 4 分钟失败无 log；1.3 `33975178` 正在构建 |
| 签名 key | `2F96685F99925C8797DD521B308DCCA0A8D0D841`（Launchpad 已确认） |

上传包（已签名、`dput` 成功、含 790 MB orig tar）：
`/mnt/k3work/firefox-k3/ppa/firefox_160.0+build1-0ubuntu0.26.04.1~mt1k3.1_source.changes`

PPA Phase 1 使用档案内 `clang-22 + rustc-1.91`（host `riscv64gc`，最后一个 gc 版本），
`-march=rv64gcv_zba_zfh_zvfh_zicbop_xsmtvdot`（RVV+IME1，不含 IME2），确保 X100 全核安全。
Phase 2 若要把 IME2 放进 PPA，需要先在同一个 PPA 上传最小 `clang-24` 工具链源码包；
Launchpad 预估 1–3 天构建，详见 `research/toolchain.md`。

**目前还不能从 PPA 安装**：旧 build `33970093` 卡住 >39h；diff-only 重试 `33975072` 失败；带完整 orig 的 `33975178` 正在构建，尚无二进制。已创建每 2 小时检查的监控任务；若 24h 超时仍无结果，建议在 Launchpad 页面取消后重触发。等它变成 `Successfully built` 后：
```bash
sudo add-apt-repository ppa:mymathersname-gmail/ppa
sudo apt update
sudo apt install firefox
```

## 3. 已交付：Thunderbird 160 deb（clang 24，最新稳定版）

| 项 | 值 |
|---|---|
| deb | `/mnt/k3work/firefox-k3/artifacts/tb160/thunderbird_160.0-1k3.1_riscv64.deb` |
| 大小 | 82 MB（Installed-Size 276995 KB） |
| sha256 | `53460aae7f4454db32c176d75a76ae3358f76b8129df4529ec1c67271eb195cb` |
| 版本 | `1:160.0-1k3.1`；已安装，`/usr/lib/thunderbird/thunderbird --version` → `Mozilla Thunderbird 160.0` |
| 编译器 | **clang 24.0.0**（config: `CC/CXX/HOST_CC` 全为 clang 24；构建日志 0 条 gcc 命令） |
| 构建 | Debian 159 打包基线迁移到 160 源码 + Python 3.12 + Rust 1.100 + cbindgen 0.29.4 |
| flags | `-O3 -march=rv64gcv_zba_zfh_zvfh_zicbop_xsmtvdot_xsmtvdotii -mtune=spacemit-a100`；Rust `+xsmtvdot` |
| lintian | 0 error；1 warning（appstream metadata validation） |
| headless | 启动存活到 timeout；仅 GTK icon-theme warning，无崩溃 |

**RVV/IME 扫描**（`/usr/lib/thunderbird/libxul.so`，164MB）：

```text
vmadot=0  vfwmadot=0  vsetvli=76883  vle=64979  vse=118348  vwmacc=1058
```

**结论：RVV 自动向量化大量使用，但 IME1(`vmadot`) / IME2(`vfwmadot`) 指令为 0。**
`-march=...xsmtvdot_xsmtvdotii` 只让编译器具备 IME 发射能力；Firefox/Thunderbird 源码没有 IME kernel，
编译器不会自动把普通循环变成 IME。要实现真正 IME 加速必须手写/集成 kernel（且 IME2 仅 A100 可执行）。

### 关键修复（NSS 3.120 兼容，Ubuntu 26.04 系统 NSS）
- 160 源码 + 159 Debian 打包层迁移；移除 159 旧 Debian patches 避免冲突
- 两处 `CERT_GetDERCertTrust` 用 `CERT_NewTempCertificate + CERT_GetCertTrust` 回退
- `CERT_GetDERCertTrust` 缺失、ML-KEM-1024/512、ML-DSA、`ssl_kea_kem`、`PK11_CreatePrivateKeyFromTemplate` 等 3.131 API 均做兼容
- l10n：上游 160 source tar 无 `thunderbird-l10n` 树，主 deb 正常；未生成有效语言包
- GCC 误判说明：config 里 `GCC_USE_GNU_LD=1` 只是“使用 GNU ld 选项”的标记，实际 `CC_TYPE=clang`、零 gcc 命令

## 4. 关键路径与复现


- Firefox 源码/构建：`/mnt/k3work/firefox-k3/build/firefox-160.0`
- 构建日志：`/mnt/k3work/firefox-k3/logs/build-firefox-mach.log`
- 打包日志：`/mnt/k3work/firefox-k3/logs/package-firefox.log`
- PPA 源码：`/mnt/k3work/firefox-k3/ppa/`
- PPA 源码解包验证：`/mnt/k3work/firefox-k3/ppa-verify/firefox-160.0`
- 工具链 wrapper：`/mnt/k3work/firefox-k3/toolchain/bin`
- 调研报告：`research/ime.md`、`research/toolchain.md`、`research/ppa.md`
- Thunderbird 159 源码/构建：`/mnt/k3work/firefox-k3/tb159/thunderbird-159.0`
- TB 构建日志：`/mnt/k3work/firefox-k3/logs/tb159-build11.log`
- 检查点：`CHECKPOINT.md`

### 本地重建命令（关键）
```bash
cd /mnt/k3work/firefox-k3/build/firefox-160.0
export PATH=/mnt/k3work/firefox-k3/toolchain/bin:$PATH
export DEB_BUILD_OPTIONS=parallel=8
export MOZCONFIG=$PWD/mozconfig
export MACH_BUILD_PYTHON_NATIVE_PACKAGE_SOURCE=none
export MOZBUILD_STATE_PATH=/mnt/k3work/firefox-k3/mozbuild-state
export TMPDIR=/mnt/k3work/firefox-k3/tmp
make -f debian/rules debian/stamp-makefile-build   # mach build
dpkg-buildpackage -b -us -uc -d -nc -j8            # 打包
```

## 5. 安全提醒

- 用户提供的 GitHub token 已在对话中明文暴露，**请立即吊销/重发**；本次未使用它。
- GPG 私钥与 passphrase 仅保存在本机，不要提交到仓库或外发。
- SSH 公钥尚未注册到 Launchpad；仅影响 git push，不影响 PPA dput。
