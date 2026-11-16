# Ubuntu 26.04 (resolute) riscv64 · Firefox/Thunderbird PPA 发布链路调研

- 调研时间：2026-11-14（UTC），Launchpad API 快照 2026-11-14T12:18Z
- 调研方式：只读。Launchpad 公开 API + 官方文档 + Launchpad 源码（HEAD `72ba15af7e009b17d4aa1467977127ac8392a4de`，2026-11-14）+ `launchpad-buildd` 源码（HEAD `813054dd03dc0804dd01828c188e8d64990cfddb`，2026-10-13）+ 实际 build log
- 未执行：未创建 PPA、未注册 key、未 dput、未 git push、未安装软件、未修改 `build/` 与 `sources/`、未读取/输出任何私钥内容
- 账号事实（API `https://api.launchpad.net/1.0/~mymathersname-gmail`）：`is_probationary=true`、`karma=0`、`is_ubuntu_coc_signer=false`、`ppas=0`、`gpg_keys=0`、`sshkeys=1`（RSA，id 494665）

---

## 0. 先修正一条「已知事实」（重要）

| 已知事实 | 实测结果 | 证据 |
|---|---|---|
| mozillateam PPA 已有 firefox 160.0 的 resolute riscv64 构建 | **有 build record，但状态是 `Failed to build`**，不是可用构建 | build `33925407`：`buildstate=Failed to build`；日志末尾 `ERROR: The rust compiler host (riscv64a23-unknown-linux-gnu) is not suitable for ...` |
| mozillateam PPA 已有 thunderbird 140.17.0 的 resolute riscv64 构建 | **有 build record，但状态是 `Cancelled build`**，`date_first_dispatched`/`datebuilt` 均为空（从未真正跑） | build `33860374`：`buildstate=Cancelled build` |
| 这说明 Launchpad 有 riscv64 builder | **成立**：`https://launchpad.net/builders` 当时有 **95 台** riscv64 builder（`bos03-riscv64-001..095`）；firefox 那次确实跑在 `bos03-riscv64-061` 上，约 3h40m | builders 页面 + build `33925407` 的 `builder_link` |
| PPA 只收源码包、riscv64 非默认架构 | **成立** | 见 §2.1 / §2.3 |

> 结论：**「有 riscv64 构建记录」≠「有 riscv64 可用构建」**。mozillateam 的 riscv64 构建目前是失败/取消状态，不能作为 riscv64 可用的证据；真正能证明的是 riscv64 builder 存在且会接 PPA 任务。

---

## 1. 结论（逐条回答 6 个问题）

### Q1. 2026 年普通用户 / probationary 账号能否创建 PPA？能否启用 riscv64？要签 Ubuntu CoC 吗？

| 子问题 | 结论 | 依据 |
|---|---|---|
| 普通用户能创建 PPA | **能**。Web/API 均可 | 官方文档 "Launchpad users can create PPAs via the web user interface or using the API"（`how-to/packaging/create-ppa`） |
| probationary 账号 | **代码层面没有 PPA 门禁**。`is_probationary` 的定义就是 `not is_team and karma == 0`，是「无 karma」的标签，不是封禁状态 | `lib/lp/registry/model/person.py` `is_probationary`（约 L1495-1501）；PPA 创建视图与 `validate_ppa` 均未检查它 |
| 要签 Ubuntu Code of Conduct 吗 | **不需要**。当前代码只在首次创建 PPA 时要求勾选 **PPA Terms of Use**；`is_ubuntu_coc_signer=false` 不阻止 PPA 创建 | `lib/lp/soyuz/browser/archive.py` `ArchiveActivateView`（约 L2349-2445）；`lib/lp/soyuz/model/archive.py` `validate_ppa`（L4109-4145）；PPA 模板只链接 PPA Terms |
| 能启用 riscv64 吗 | **能**。PPA 概览 → **Change details** → **Processors** 勾选 `riscv64` → Save。riscv64 不是管理员专属 restricted 架构（大量普通用户 PPA 正在 riscv64 上构建） | 文档 `reference/packaging/ppas/ppa` 架构表；`https://launchpad.net/builders` 上 11 个不同 PPA owner 的 riscv64 构建；代码 `setProcessors` 只校验 `proc.restricted`（管理员可改） |
| 新 PPA 默认架构 | **只有 amd64**（`build_by_default`）；riscv64 必须手工启用 | 文档架构表 `riscv64 — Built by default: no`；`ArchiveSet.new()` 默认取 `p.build_by_default`（`archive.py` 约 L4436-4442） |

**确切 UI 路径与 URL**（本账号）：

| 动作 | URL |
|---|---|
| 个人主页 | `https://launchpad.net/~mymathersname-gmail` |
| 创建 PPA（页面标题 "Activate a Personal Package Archive"） | `https://launchpad.net/~mymathersname-gmail/+activate-ppa` |
| PPA 概览（创建后） | `https://launchpad.net/~mymathersname-gmail/+archive/ubuntu/<ppa-name>` |
| 修改 PPA / 勾选 Processors | `https://launchpad.net/~mymathersname-gmail/+archive/ubuntu/<ppa-name>/+edit` |
| 编辑 PPA 依赖 | `https://launchpad.net/~mymathersname-gmail/+archive/ubuntu/<ppa-name>/+edit-dependencies` |
| 导入 OpenPGP key | `https://launchpad.net/~mymathersname-gmail/+editpgpkeys` |
| 导入 SSH key | `https://launchpad.net/~mymathersname-gmail/+editsshkeys` |
| PPA Terms（首次创建必须勾选） | `https://ubuntu.com/docs/launchpad/user/reference/launchpad-and-community/legal/launchpad-policies#personal-package-archive-eligibility` |

**probationary 的实际影响**：只在源码/模板里看到 `linkify_text = not owner.is_probationary` 这类展示层用法（`browser/archive.py` 约 L1131），没有找到任何阻止 PPA 创建/上传/启架构的判断。**注意**：本次没有实际提交创建表单（任务禁止），所以「能创建」是代码 + 文档证据，不是实测；账号邮箱是否已确认无法从匿名 API 判断（`hide_email_addresses=true`，`confirmed_email_addresses` 匿名返回 0）。

**另一个关键顺序**：`setProcessors` 本身只增删 `ArchiveArch`，代码里未见为已发布源码补建新架构 build 的逻辑（`archive.py` L3793-3846）；因此按「先启用、后上传」执行。所以 **riscv64 必须在上传源码之前启用**，否则该次上传不会产生 riscv64 build，只能改版本号重传或 copy。

### Q2. 创建 PPA / 注册 GPG / 注册 SSH 的精确步骤；PPA 上传用 dput 还是 git push？

**(a) 注册 OpenPGP key（上传签名必需）**

1. 本机生成签名 key（示例，RSA 4096，仅签名）：`gpg --quick-gen-key "Yeqin Su <your@email>" rsa4096 sign 2y`
2. 发布到 Ubuntu keyserver：`gpg --keyserver hkps://keyserver.ubuntu.com --send-keys <FPR>`
3. 打开 `https://launchpad.net/~mymathersname-gmail/+editpgpkeys`（会要求重新登录），粘贴 **完整 fingerprint**，Launchpad 到 keyserver 取 key。
4. Launchpad 会给你发一封 **用该 key 加密的确认邮件**；本机 `gpg --decrypt` 解出链接并打开，完成导入。
   - 文档：`https://ubuntu.com/docs/launchpad/user/how-to/import-openpgp-key`
   - 代码：`PersonGPGView.initialize` 调用 `require_fresh_login`；模板提示 key 必须已在 Ubuntu keyserver（传播可能约 1 小时）。

**(b) 注册 SSH key（git push / SFTP 需要；FTP dput 不需要）**

1. `cat ~/.ssh/id_ed25519.pub`
2. 打开 `https://launchpad.net/~mymathersname-gmail/+editsshkeys`，粘贴公钥，点 **Import public key**。
3. 验证：`ssh -o IdentitiesOnly=yes -i ~/.ssh/id_ed25519 git@git.launchpad.net`（应能识别你的账号；不是普通 shell）。
   - 文档：`https://ubuntu.com/docs/launchpad/user/how-to/import-ssh-keys`
   - **本账号现状**：API 显示已有 1 个 RSA SSH key（id 494665），本机 ed25519 未注册，所以 `git@git.launchpad.net` 报 "doesn't have a registered SSH key"。加上 ed25519 即可。

**(c) 创建 PPA**

1. 登录后打开 `https://launchpad.net/~mymathersname-gmail/+activate-ppa`。
2. 填 name / displayname / description；首次必须勾 **"I have read and accepted the PPA Terms of Use."**。
3. 点 **Activate**；成功后 PPA 出现在 profile 的 Personal Package Archives。
4. 打开 `.../+archive/ubuntu/<ppa>/+edit` → **Processors** 勾 `riscv64` → Save。
   - 文档：`https://ubuntu.com/docs/launchpad/user/how-to/packaging/create-ppa`

**(d) PPA 上传：dput，不是 git push**

```bash
# 1) 源码包（source-only）
dpkg-buildpackage -S -I -i -nc -d
# 或 debuild -S -sa（新包）/ debuild -S -sd（沿用 Ubuntu 已有 orig.tar）
# 2) 签名（若上一步没签）
debsign -k <KEYID> ../<pkg>_<version>_source.changes
# 3) 上传
dput ppa:mymathersname-gmail/<ppa> ../<pkg>_<version>_source.changes
```

- Launchpad **只接受源码包**，明确拒绝 `.deb`（"Launchpad builds the packages onsite, and does not accept deb files"）。
- 目标 series 由 `debian/changelog` 的 `Distribution` 字段决定（必须是 `resolute`，否则上传被拒）；PPA 只接受 **Release** pocket（代码 `Archive.getPockets` 对 PPA 返回 `[RELEASE]`，`archive.py` 约 L3848-3853）。
- 自定义 `~/.dput.cf`（文档原样）：
  ```ini
  [my-ppa]
  fqdn = ppa.launchpad.net
  method = ftp
  incoming = ~mymathersname-gmail/ubuntu/<ppa>/
  login = anonymous
  allow_unsigned_uploads = 0
  ```
- 本机已装 `dput`/`dpkg-buildpackage`/`debsign`/`gpg`；系统 `/etc/dput.cf` 已有 `[ppa]` target（`incoming = ~%(ppa)s`），所以 `dput ppa:user/ppa` 可用。

**git+ssh 与 PPA 的关系**：两者**完全独立**。

- `git push` 到 `git.launchpad.net` 只是代码托管；**不会**上传/发布任何 deb。
- PPA 发布链路是 `signed source package → dput (FTP/SFTP) → Launchpad 构建 → 发布`。
- 唯一的桥是 **source package recipe / daily build**：把 git 分支 + recipe 交给 Launchpad，由它自动构建到 PPA（`https://ubuntu.com/docs/launchpad/user/how-to/source-package-recipe`）。这条路由不经过 dput，但对 Firefox 这种带巨大 orig.tar 的包并不省事；本次发布链路用 dput 更直接。
- SFTP 方式 dput 会复用 SSH key；FTP 方式用 `login = anonymous`，不依赖 SSH key。

### Q3. PPA 的 riscv64 构建资源/超时/配额

| 项目 | 结论 | 证据 |
|---|---|---|
| 单次 build 最长时间 | **没有找到官方公布的硬性上限**；`launchpad-buildd` 代码里没有 build 时长超时（只有取消时的 `abort_timeout=120` 秒）。实测 **Thunderbird riscv64 构建 34h35m56s 成功**；builders 页面上还有已跑 **41 小时**仍未结束的 riscv64 构建 | `lpbuildd/builder.py:153`；`launchpad-buildd` HEAD `813054d`；build `33456149` sbuild `Package-Time: 124556`；`https://launchpad.net/builders` 快照 |
| 并行 build 数 | **未见按 PPA 的并发上限**（文档/代码均未找到）。实测同一 PPA、同一源码的 **7 个架构在 8 秒内被同时 dispatch**（firefox 160.0：amd64/amd64v3/arm64/armhf/ppc64el/riscv64/s390x，09:53:06–09:53:13） | build `33925402`–`33925408` 的 `date_first_dispatched` |
| 排队等待 | 存在，且可能很长：Thunderbird 140.13.0 从 `datecreated 07:22` 到 `date_first_dispatched 09:40`（约 2h18m）；firefox 160.0 只等了约 13 秒 | build `33456149` / `33925407` |
| PPA 磁盘配额 | **默认 8 GiB/PPA**（public；private 20 GiB）。可申请提高：mozillateam 的 PPA 实测 `authorized_size=81920`（= 80 GiB） | 文档 quotas 表；代码 `ArchiveSet.new`：`20480 if private else 8192`（MiB）；API `~mozillateam/+archive/ubuntu/ppa` 的 `authorized_size` |
| 源码包大小限制 | **没有按包的硬限制**；官方问答明确 "there isn't any arbitrary limit besides the 8Gb limit on the size of the PPA"。上传时按 `.changes` 文件总大小累计检查 PPA 配额 | Launchpad question #818912（2024-10）；`uploadpolicy.py` `checkArchiveSizeQuota`（L218-250） |
| 二进制大小限制 | 未见按二进制的文档化上限；已发布源码+二进制+调试符号都计入同一个 8 GiB PPA 配额 | 文档 quotas / `estimated_size` 机制 |
| 构建机磁盘 | 与 PPA 配额无关；实测 Thunderbird riscv64 构建用 **28873408 KiB ≈ 27.5 GiB**，Firefox 失败那次 **6326468 KiB ≈ 6.0 GiB** | 两份 build log 的 sbuild Summary |
| 构建机数量 | 2026-11-14T12:18Z：440 台 builder，其中 **95 台 riscv64**（`bos03-riscv64-001..095`），215 台正在构建 | `https://launchpad.net/builders` |

> 结论：**不要按 2h/4h 规划**。riscv64 重包单次构建按「一天」量级预算；并发不是瓶颈（至少 7 路），瓶颈是单机速度与共享队列。
> 说明：`41h` 的 kicad 构建属于 Ubuntu 主档案（不是 PPA），但同一 build farm；它至少证明没有 41h 以内的硬超时。是否存在更长（如 48h/72h）的隐藏上限：**未证实**。

### Q4. 从 API 取 mozillateam firefox riscv64 build record / log，估算构建耗时

**API 调用（可直接复现）**

```bash
H='Accept: application/json'
# 1) 找 resolute 的已发布源码
curl -s -H "$H" 'https://api.launchpad.net/1.0/~mozillateam/+archive/ubuntu/ppa?ws.op=getPublishedSources&source_name=firefox&exact_match=true&status=Published'
#    → firefox 160.0+build1-0ubuntu0.26.04.1~mt1, distro_series_link=.../ubuntu/resolute, sourcepub 18931053
# 2) 取 build record（本次 riscv64 build id 33925407；直接按 id 取最可靠）
curl -s -H "$H" 'https://api.launchpad.net/1.0/~mozillateam/+archive/ubuntu/ppa/+build/33925407'
# 3) 下载 build log（公开）
curl -sL 'https://launchpad.net/~mozillateam/+archive/ubuntu/ppa/+build/33925407/+files/buildlog_ubuntu-resolute-riscv64.firefox_160.0+build1-0ubuntu0.26.04.1~mt1_BUILDING.txt.gz' | gunzip
```

**关键字段**（build `33925407`）：

| 字段 | 值 |
|---|---|
| `title` | `riscv64 build of firefox 160.0+build1-0ubuntu0.26.04.1~mt1 in ubuntu resolute RELEASE` |
| `buildstate` | `Failed to build` |
| `date_first_dispatched` | `2026-11-07T09:53:13.798907+00:00` |
| `datebuilt` | `2026-11-07T13:33:48.837384+00:00`（含清理；wall ≈ **3h40m35s**） |
| `builder_link` | `https://api.launchpad.net/1.0/builders/bos03-riscv64-061` |
| `build_log_url` | 上述 `.../buildlog_ubuntu-resolute-riscv64..._BUILDING.txt.gz` |

**sbuild Summary（日志尾部）**：

```
Build Architecture: riscv64
Build-Space: 6326468
Build-Time: 8963          # 2h29m23s
Distribution: resolute
Install-Time: 1207        # 20m07s
Package-Time: 11639       # 3h13m59s
Status: attempted
Build needed 03:13:59, 6326468k disk space
E: Build failure (dpkg-buildpackage died)
```

**失败原因（不是超时/配额）**：

```
checking rustc version... 1.97.1
checking for rust host triplet...
ERROR: The rust compiler host (riscv64a23-unknown-linux-gnu) is not suitable for the configure host (riscv64-unknown-linux-gnu/riscv64gc-unknown-linux-gnu).
```

构建在 `mach configure` 阶段失败；在它之前，`cbindgen` / `dump_syms` 等 cargo 步骤耗掉了大部分时间（日志中 `dump_syms` 单段就 `Finished ... in 26m 42s`，10:08 开始 dpkg-buildpackage、13:17 左右才进 configure），所以 **3h14m 不是 Firefox 完整构建耗时**，只是失败前的耗时。

**同源码其它架构（对照，成功）**：

| 架构 | dispatch → built | 结果 |
|---|---|---|
| amd64 | 09:53:06 → 11:23:49（**1h30m44s**） | Successfully built |
| arm64 | 09:53:11 → 11:45:59（1h52m48s） | Successfully built |
| ppc64el | 09:53:13 → 12:41:26（2h48m13s） | Successfully built |
| s390x | 09:53:12 → 10:50:52（57m40s） | Successfully built |
| riscv64 | 09:53:13 → 13:33:48（3h40m35s） | **Failed to build** |

**Thunderbird 的真实 riscv64 成功样本**（mozillateam PPA，noble）：

| 字段 | 值 |
|---|---|
| build | `33456149`（`riscv64 build of thunderbird 1:140.13.0+build1-0ubuntu0.24.04.1~mt1 in ubuntu noble RELEASE`） |
| `buildstate` | `Successfully built` |
| dispatch → built | `2026-07-31T09:40:42` → `2026-08-01T20:53:09`（**35h12m28s**） |
| sbuild | `Build-Time: 121945`（**33h52m25s**）、`Package-Time: 124556`（**34h35m56s**）、`Build-Space: 28873408`（≈27.5 GiB） |
| 发布 | 该 build 的二进制被 **copy** 到 `resolute/riscv64`（binarypub `247713663` 的 `build_link` 指向 `33456149`，title 是 noble） |

**发布现状**：

- firefox：`getPublishedBinaries(binary_name=firefox)` 过滤 `riscv64` → **0 条**（即 PPA 里没有可用 riscv64 firefox 二进制）。
- thunderbird：riscv64 仅 `1:140.13.0+...` 的 resolute/noble 两条，**140.17.0 无 riscv64 二进制**（对应 build 33860374 是 Cancelled）。
- Ubuntu 主档案 riscv64 仅有 tenacious/stonking 的 `firefox 1:1snap1-0ubuntu11`（snap 启动器 stub）；`resolute` 没有 firefox riscv64 二进制，且该包**不是真实 Firefox 构建**。

**耗时估算**：

- Thunderbird riscv64：**实测 34h36m（sbuild Package-Time）**，可作为同量级 Gecko 包的锚点。
- Firefox riscv64：**无成功样本**；按 Thunderbird 同量级 + Firefox amd64 1h31m 推断，成功构建预计 **≥ 1 天（约 30–40h 量级）**。这是**估算，未证实**；且必须先解决 rust host triple 的 configure 失败，否则根本走不到编译阶段。

**API 坑（实测）**：PPA 的 `getBuildRecords` 中 `source_name` 有效（无过滤 12753 条；`source_name=firefox` 8900 条，`source_name=thunderbird` 3628 条），但 `arch_tag` / `source_version` / `status` **不生效**（传了仍返回 8900 条、含其它架构）。可靠做法是：先 `getPublishedSources` 拿版本，再按已知 build id 取 `+build/<id>`，或用 `jq 'select(.arch_tag=="riscv64")'` 客户端过滤。

### Q5. PPA 能否依赖另一个 PPA 的包？clang-24 作为 Firefox Build-Depends 的正确做法

**能。** 官方文档明确：PPA 构建满足 Build-Depends 的顺序是

1. **你正在上传到的这个 PPA 里最新的包**；
2. 主 Ubuntu archive 的 main/restricted/universe/multiverse；
3. **可选：其它 Launchpad PPA**（PPA 页面 → Edit PPA dependencies → Add PPA dependency，pin priority `-100..2000`，默认 `500`）。

证据：
- `https://ubuntu.com/docs/launchpad/user/reference/packaging/ppas/building-a-source-package` 的 "Dependencies" 段。
- `https://ubuntu.com/docs/launchpad/user/how-to/packaging/create-ppa` 的 "Manage archive dependencies" 段（含 API `addArchiveDependency(dependency=..., pocket="Release", pin_priority=...)`）。
- 实测日志：firefox build 的 `override-sources-list` 里同时有 `deb http://ppa.launchpadcontent.net/mozillateam/ppa/ubuntu resolute main`（**本 PPA 自己**）、`ricotz/mozilla`、`rust-toolchain/staging`、`ubuntu-mozilla-security` 和主 archive —— 直接证明「本 PPA 自己的包会进 build chroot」。

**clang-24 的正确做法（按推荐顺序）**：

1. **同 PPA 方案（最省事，推荐）**：先在同一个 PPA 里上传 `clang-24`/LLVM 源码包（riscv64 已启用），等它的 `clang-24`、`libclang-common-24-dev` 等在 **resolute/riscv64** 状态变成 `Published`；再上传 Firefox 源码（`Build-Depends: clang-24, ...` 或 `debian/rules` 里 `CC=clang-24`）。Firefox 构建会自动从本 PPA 解析到 clang-24。
2. **独立 toolchain PPA + 依赖**：如果 clang-24 已经在某个 PPA 里有 riscv64 构建，直接在你的 PPA 的 **Edit PPA dependencies** 里加上它（或者 API `addArchiveDependency`），再上传 Firefox。
3. **不要**想上传本地编译好的 clang `.deb`：PPA 拒绝预编译二进制（文档 "Uploadable artefacts: Source packages only; pre-built binary uploads are rejected"）。若别的 Launchpad PPA 已有 riscv64 clang-24 二进制，可以用 **Copy packages**（支持跨 series、可勾选 "copy related binary package"）复制到你自己的 PPA。

**顺序/坑**：

- 必须**先启用 riscv64**，再上传；`setProcessors` 本身不补建 build（未见补建逻辑）。
- 工具链没发布前上传 Firefox，build 会停在 `Dependency wait`（thunderbird 列表里就有这种状态）。稳妥做法是等工具链 `Published` 再传 Firefox；若已经 wait，可用 build 页面的 Retry（需 owner 登录）。
- PPA 依赖只能加 **Launchpad 上的 archive/PPA**，不能填任意第三方 apt 源 URL。
- 默认 pin 500 与主 archive 相同，依赖 PPA 里若有更新版本的同名包会覆盖主 archive，注意只加可信 toolchain PPA。

### Q6. 最小人工步骤 vs 机器可自动完成

**人工（必须浏览器/邮件，按顺序）**

1. 登录 Launchpad：`https://launchpad.net/~mymathersname-gmail`
2. 导入 GPG：`https://launchpad.net/~mymathersname-gmail/+editpgpkeys`（粘贴 fingerprint；解密确认邮件并点链接）
3. 导入 SSH 公钥：`https://launchpad.net/~mymathersname-gmail/+editsshkeys`（仅 git push/SFTP 需要）
4. 创建 PPA 并勾选 ToS：`https://launchpad.net/~mymathersname-gmail/+activate-ppa`
5. 启用 riscv64：`https://launchpad.net/~mymathersname-gmail/+archive/ubuntu/<ppa>/+edit` → Processors
6. （如需自建 clang-24）先上传工具链源码并等 riscv64 `Published`：`dput ppa:mymathersname-gmail/<ppa> clang-24_*.changes`
7. 上传 Firefox 源码：`dput ppa:mymathersname-gmail/<ppa> firefox_*_source.changes`
8. 在 PPA 的 "View package details / View all builds" 看 build；失败就修工具链/改版本号重传

**机器可自动（不需要浏览器，或在拿到授权后）**

- `gpg --quick-gen-key` / `gpg --armor --export` / `gpg --keyserver hkps://keyserver.ubuntu.com --send-keys`（生成本地 key、发布公钥）
- `dpkg-buildpackage -S -I -i -nc -d` + `debsign -k<KEYID>`（生成并签名 source package）
- `dput ppa:mymathersname-gmail/<ppa> ../*.changes`（上传；需要已注册 GPG key + PPA 已建）
- 轮询构建状态/下载日志：`curl -H 'Accept: application/json' https://api.launchpad.net/1.0/~mymathersname-gmail/+archive/ubuntu/<ppa>/+build/<id>`
- `git push`（SSH key 注册后；只影响代码托管，不影响 PPA 上传）
- 可选：`lppa create <ppa> riscv64` 或 `lp-shell` 的 `createPPA`/`setProcessors`（需要 OAuth 授权；本次未使用，因为任务禁止创建 Launchpad 资源）

---

## 2. 证据

### 2.1 PPA 架构 / 配额 / 只收源码（官方文档）

- `https://ubuntu.com/docs/launchpad/user/reference/packaging/ppas/ppa`
  - 目标 series 从 `debian/changelog` 的 `Distribution` 字段读取，未知/不支持的 series 会导致上传被拒
  - 架构表：`riscv64 — Built by default: no`；`amd64 — yes`；`arm64/ppc64el/s390x/... — no`
  - Quotas：`Disk space 8 GiB; larger quotas considered on request at https://answers.launchpad.net/launchpad`；`Uploadable artefacts: Source packages only; pre-built binary uploads are rejected`
  - Signing key：Launchpad 为每个 owner 的默认 PPA 生成并复用一把 GPG key
- `https://ubuntu.com/docs/launchpad/user/how-to/packaging/ppa-package-upload`
  - `dput ppa:your-lp-id/ppa <source.changes>`；`debuild -S`；"Launchpad builds the packages onsite, and does not accept deb files"
  - `~/.dput.cf` 模板（`fqdn = ppa.launchpad.net`, `method = ftp`, `incoming = ~<id>/ubuntu/<ppa>/`, `login = anonymous`, `allow_unsigned_uploads = 0`）
- `https://ubuntu.com/docs/launchpad/user/how-to/packaging/build-deb-packages-in-launchpad`
  - 前置条件：**OpenPGP key registered**（`https://launchpad.net/~/+editpgpkeys`）、PPA、`devscripts dpkg-dev dput`
  - `dpkg-buildpackage -S -I -i -nc -d` → `debsign -k <key>` → `dput ppa:<username>/<ppa> ...`
- `https://ubuntu.com/docs/launchpad/user/reference/packaging/ppas/building-a-source-package`
  - 版本号：`~ppa1` / `~ubuntu26.04.1`；同一版本不能重复上传
  - Dependencies：本 PPA + 主 archive + 可选其它 PPA
- `https://ubuntu.com/docs/launchpad/user/reference/launchpad-and-community/legal/launchpad-policies#personal-package-archive-eligibility`
  - PPA 内容需 OSI/FSF/DFSG 等许可（Firefox 是 MPL-2.0，属 OSI approved，符合）
  - Canonical 保留对 disk/CPU/bandwidth 的配额权利

### 2.2 创建/编辑 PPA 的代码路径（无 CoC、无 karma 门禁）

源码（只读，HEAD `72ba15af...`）：

- 创建视图：`https://git.launchpad.net/launchpad/plain/lib/lp/soyuz/browser/archive.py`
  - `ArchiveActivateView`（约 L2349-2445）：首次创建时增加 `accepted` 复选框（"I have read and accepted the PPA Terms of Use."），`validate()` 只校验该复选框 + `validate_ppa`；**没有 CoC / karma / probationary 检查**。
  - 路由：`name="+activate-ppa"`，`permission="launchpad.Edit"`，`for="IPerson"`（`lib/lp/soyuz/browser/configure.zcml` 约 L545-550）→ 自己的 profile 自动有权限。
  - 页面模板 `archive-activate.pt` 只链接 PPA help 与 PPA Terms。
- 校验：`https://git.launchpad.net/launchpad/plain/lib/lp/soyuz/model/archive.py`
  - `validate_ppa`（L4109-4145）：只拒绝 private 无权限、open team、distribution 不支持 PPA、名称冲突（"ubuntu"/distribution 名）；**没有 CoC**。
  - `archive.py` L4432：`authorized_size = 20480 if private else 8192`（MiB）→ 公开 PPA 默认 **8 GiB**。
  - L4436-4442：`processors is None` 时取所有 `build_by_default` → 默认只有 amd64。
  - `setProcessors`（L3793-3846）：只增删 `ArchiveArch`，代码里未见为已有 source 补建 build 的逻辑；非 admin 只能改 `not proc.restricted` 的处理器。
- probationary 定义：`https://git.launchpad.net/launchpad/plain/lib/lp/registry/model/person.py`
  - L1495-1501：`return not self.is_team and self.karma == 0`
  - L3821 `createPPA()` → `validate_ppa` → `IArchiveSet.new(...)`；无 CoC 参数
  - L3951 `canCreatePPA()` 是 team 的 membership policy 判断，不用于 person 的 `+activate-ppa` 视图
- 上传配额检查：`https://git.launchpad.net/launchpad/plain/lib/lp/archiveuploader/uploadpolicy.py`
  - `checkArchiveSizeQuota`（L218-250）：把 `.changes` 里所有文件大小累加，超过 `authorized_size` 就 reject；95% 时 warn。

### 2.3 构建资源 / 超时 / 并发（实测 + 源码）

- builders 快照（2026-11-14T12:18Z，`https://launchpad.net/builders`）：
  - `440 registered build machines: 440 available (215 building, 34 cleaning, 191 idle)`；
  - riscv64 建筑机 **95 台**（`bos03-riscv64-001..095`）；
  - riscv64 区当前有 **11 个不同 PPA owner** 的构建：`blkerby, canonical-kernel-team, joseluisblancoc, karljs, profzoom, rhscz, ryancarlson12, ubuntu-desktop, videolan, vpa1977, xtradeb`（证明普通用户可启用 riscv64）；
  - 两个长构建：`kicad ... (for 41 hours)`（主档案）、`linux-riscv-7.0 ... [~canonical-kernel-team/ubuntu/ppa] (for 18 hours)`（PPA）。
- `launchpad-buildd`（HEAD `813054d`，2026-10-13）：
  - `lpbuildd/builder.py:153`：`self.abort_timeout = 120`（取消时等 120s，不是 build 超时）；
  - 全仓 grep 未发现 build 时长上限；`sbuildrc` 的 `stalled_pkg_timeout = 150` 是 apt 的 stalled 提示，不是构建超时。
  - 结论：**没有可引用的官方 build 时长上限**；实测 34h36m 成功、41h 仍在跑。
- 并发：firefox 160.0 的 7 个架构 build 在 `09:53:06–09:53:13` 全部 `date_first_dispatched`（build 33925402-408）。
- PPA 配额实测：`~mozillateam/+archive/ubuntu/ppa` 与 `firefox-next` 的 `authorized_size=81920`（80 GiB）；普通用户新 PPA 默认 8192（8 GiB），见 `~issinoho/ubuntu/loadbearer`、`~w-rouesnel/ubuntu/tmux-tabbed-terminal`。
- 源码大小：Launchpad question #818912（2024-10-04，Ines Almeida）："Afaik there isn't any arbitrary limit besides the 8Gb limit on the size of the PPA - thought I don't think we test very large file uploads."（`https://launchpad.net/launchpad/+question/818912`）

### 2.4 mozillateam 的 build record / log（本次核心证据）

| 查询 | URL |
|---|---|
| 已发布源码 | `https://api.launchpad.net/1.0/~mozillateam/+archive/ubuntu/ppa?ws.op=getPublishedSources&source_name=firefox&exact_match=true&status=Published` |
| firefox 160.0 riscv64 build | `https://api.launchpad.net/1.0/~mozillateam/+archive/ubuntu/ppa/+build/33925407` |
| firefox 160.0 amd64 build | `.../+build/33925402` |
| thunderbird 140.17.0 resolute riscv64 | `.../+build/33860374`（Cancelled） |
| thunderbird 140.13.0 noble riscv64（成功样本） | `.../+build/33456149` |
| riscv64 二进制（thunderbird） | binarypub `247713663` → `build_link=.../+build/33456149` |
| firefox 已发布 riscv64 二进制 | `...?ws.op=getPublishedBinaries&binary_name=firefox&exact_match=true` → riscv64 0 条 |

日志原文（firefox `33925407`，尾部）：

```
checking rustc version... 1.97.1
checking for rust host triplet...
ERROR: The rust compiler host (riscv64a23-unknown-linux-gnu) is not suitable for the configure host (riscv64-unknown-linux-gnu/riscv64gc-unknown-linux-gnu).
...
Build-Time: 8963
Install-Time: 1207
Package-Time: 11639
Build needed 03:13:59, 6326468k disk space
E: Build failure (dpkg-buildpackage died)
```

Thunderbird `33456149`，日志尾部：

```
Build Architecture: riscv64
Build-Space: 28873408
Build-Time: 121945
Distribution: noble
Install-Time: 1122
Package-Time: 124556
Status: successful
Build needed 34:35:56, 28873408k disk space
```

### 2.5 账号/密钥现状（API）

```
GET https://api.launchpad.net/1.0/~mymathersname-gmail
  is_probationary=true, karma=0, is_ubuntu_coc_signer=false, ppas=0
GET .../gpg_keys        → total_size 0
GET .../sshkeys         → total_size 1, keytype RSA, self_link .../+ssh-keys/494665
GET .../ppas            → total_size 0
```

→ GPG 0 把：上传前必须注册；SSH 已有 1 把旧 RSA，本机 ed25519 未注册，故 `git@git.launchpad.net` 失败。

---

## 3. 风险

1. **Firefox riscv64 当前会先在 configure 挂掉（P0）**：`rustc-1.97` 报告的 host 是 `riscv64a23-unknown-linux-gnu`，与 `riscv64-unknown-linux-gnu/riscv64gc` 不匹配。这是工具链/打包问题，不是配额/超时；不修它，PPA 构建必然失败。需要换一把 host 为 `riscv64gc-unknown-linux-gnu` 的 rustc，或 patch `configure`/`mozconfig`（风险更高，需验证）。
2. **构建时间按天计（P1）**：Thunderbird riscv64 实测 34h36m；Firefox 同量级，预计 ≥1 天，且 PPA 排队可能再加数小时。每次失败重传都要 bump 版本号，迭代成本高。
3. **8 GiB 配额（P1）**：Firefox 源码 + 二进制 + 多版本/多架构会快速吃掉 8 GiB；可像 mozillateam 一样申请到 80 GiB（`answers.launchpad.net/launchpad`），但要提前申请。
4. **不能上传预编译 clang-24（P1）**：只能源码上传/在 Launchpad 构建，或从已有 PPA copy 二进制；自建 clang-24 自身也是一个数小时级 riscv64 构建。
5. **riscv64 启用顺序（P1）**：`setProcessors` 本身不补建 build（未见补建逻辑）；必须先启用再传源码，否则可能白传一次。
6. **GPG/SSH 注册有延迟（P2）**：keyserver 传播可能约 1 小时；GPG 导入需要解密确认邮件；未注册 key 的 `.changes` 会被拒。
7. **依赖 PPA 的 pin 500（P2）**：依赖 PPA 会整体进入 build chroot，可能覆盖主 archive 同名包；只加可信工具链 PPA，必要时调 pin。
8. **probationary 标签与 ToS（P2）**：`karma=0` 只影响展示；但 PPA 内容仍需满足许可（MPL-2.0 OK）与反滥用条款；大量/异常构建可能被 Canonical 限流。
9. **未实测项**：本次没有实际创建 PPA（任务禁止），Q1 的「能创建」是代码+文档证据；账号邮箱验证状态匿名不可见；是否存在 >41h 的隐藏 build 上限未证实。

---

## 4. 操作清单

### 4.1 用户手工最小步骤（每步 1 行，含 URL）

1. 登录 Launchpad：`https://launchpad.net/~mymathersname-gmail`
2. 注册 GPG（粘贴 fingerprint，解密确认邮件）：`https://launchpad.net/~mymathersname-gmail/+editpgpkeys`
3. 注册本机 ed25519 公钥（git push/SFTP 才需要）：`https://launchpad.net/~mymathersname-gmail/+editsshkeys`
4. 创建 PPA 并勾选 PPA Terms of Use：`https://launchpad.net/~mymathersname-gmail/+activate-ppa`
5. 在 Processors 里勾选 riscv64：`https://launchpad.net/~mymathersname-gmail/+archive/ubuntu/<ppa>/+edit`
6. （如需 clang-24）先 `dput` 工具链源码，等 riscv64 `Published`：`https://launchpad.net/~mymathersname-gmail/+archive/ubuntu/<ppa>`
7. `dput ppa:mymathersname-gmail/<ppa> firefox_*_source.changes`
8. 在 `+builds` 页面盯 build / 下载日志；失败改工具链后 bump 版本号重传

### 4.2 机器上可自动完成（无需浏览器/已获授权时）

```bash
# 0) 本机工具已具备（本次已验证）：dput dpkg-buildpackage debsign gpg
# 1) 生成并发布 GPG（若还没有）
gpg --quick-gen-key "Yeqin Su <your@email>" rsa4096 sign 2y
FPR=$(gpg --list-keys --with-colons "Yeqin Su" | awk -F: '/^fpr/{print $10; exit}')
gpg --keyserver hkps://keyserver.ubuntu.com --send-keys "$FPR"
# 2) 源码包 + 签名
dpkg-buildpackage -S -I -i -nc -d
debsign -k "$FPR" ../firefox_*_source.changes
# 3) 上传
dput ppa:mymathersname-gmail/<ppa> ../firefox_*_source.changes
# 4) 轮询构建（匿名可读）
curl -s -H 'Accept: application/json' \
  'https://api.launchpad.net/1.0/~mymathersname-gmail/+archive/ubuntu/<ppa>/+build/<id>' | jq '{buildstate,date_first_dispatched,datebuilt,build_log_url}'
```

### 4.3 验收信号（做完怎么算闭环）

- `+edit` 页面 Processors 中 riscv64 已勾选并保存（页面回显）；
- `getPublishedSources` 能看到你的 source 在 `resolute` 且 `status=Published`；
- `+builds` 出现 `riscv64` build 且 `buildstate` 从 `Needs building` → `Currently building` → `Successfully built`；
- `getPublishedBinaries` 过滤 `resolute/riscv64` 返回你的 binary 且 `status=Published`；
- 用户端 `add-apt-repository ppa:mymathersname-gmail/<ppa> && apt install firefox` 可解析到你的版本。

---

## 附录 A：时间换算（本报告用到的）

| 量 | 秒 | 换算 |
|---|---|---|
| firefox 160.0 amd64 dispatch→built | 5443.68 | 1h30m44s |
| firefox 160.0 riscv64 dispatch→built（失败） | 13235.04 | 3h40m35s |
| firefox 160.0 riscv64 sbuild Package-Time | 11639 | 3h13m59s |
| firefox 160.0 riscv64 sbuild Build-Time | 8963 | 2h29m23s |
| thunderbird 140.13.0 riscv64 dispatch→built | 126747.59 | 35h12m28s |
| thunderbird 140.13.0 riscv64 sbuild Package-Time | 124556 | 34h35m56s |
| thunderbird 140.13.0 riscv64 sbuild Build-Time | 121945 | 33h52m25s |

## 附录 B：未证实 / 不可证实项

- 本账号实际提交创建 PPA 的成功性（任务禁止实际创建）→ 代码/文档推断为「可以」。
- 账号邮箱验证状态（匿名 API 隐藏）→ 未证实。
- build 是否存在 >41h 的隐藏硬超时 → 未找到文档/代码，未证实存在。
- Firefox riscv64 成功构建耗时 → 无成功样本，仅按 Thunderbird 估算。
- mozillateam 的 80 GiB 配额是否为「申请而来」→ 默认 8 GiB + 实测 80 GiB + 文档可申请，推断为申请，未证实流程。
- `riscv64` 处理器在 DB 里是否 `restricted=false`（API 不暴露该字段）→ 由 11 个普通用户 PPA 正在构建 riscv64 反推，未直接读到 flag。
