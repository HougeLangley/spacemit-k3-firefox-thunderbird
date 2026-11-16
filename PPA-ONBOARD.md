# K3 Firefox PPA — 上线清单（需要你手工完成的 4 步）

账号：`mymathersname-gmail`（Yeqin Su）
PPA URL 名：`ppa`（display name：`firefox-k3`）
目标：Ubuntu 26.04 `resolute` / `riscv64`
签名 key：`2F96685F99925C8797DD521B308DCCA0A8D0D841`
公钥文件：`/mnt/k3work/firefox-k3/ppa-keys/ppa-signing-key.asc`
私钥密码文件：`/mnt/k3work/firefox-k3/ppa-keys/passphrase`（600，勿提交/勿外发）
撤销证书：`~/.gnupg/openpgp-revocs.d/2F96685F99925C8797DD521B308DCCA0A8D0D841.rev`

> 本机已经：生成 RSA4096 签名 key、发布到 `hkps://keyserver.ubuntu.com`、生成并签名
> `firefox_160.0+build1-0ubuntu0.26.04.1~mt1k3.1_source.changes`（含 790MB orig tar）。
> 还差 Launchpad 侧的账号动作。

## 1. 注册 GPG key（必须）

1. 打开 <https://launchpad.net/~mymathersname-gmail/+editpgpkeys>，重新登录。
2. 粘贴完整 fingerprint：`2F96685F99925C8797DD521B308DCCA0A8D0D841`。
3. Launchpad 会从 Ubuntu keyserver 取 key，并给你发一封 **用该 key 加密的确认邮件**。
4. 把邮件保存为 `confirm.eml`，在本机执行：
   ```bash
   gpg --decrypt confirm.eml
   ```
   打开邮件里的确认链接，完成导入。
5. 若 keyserver 尚未传播（通常几分钟到 1 小时），稍后重试；也可本机再次：
   ```bash
   gpg --keyserver hkps://keyserver.ubuntu.com --send-keys 2F96685F99925C8797DD521B308DCCA0A8D0D841
   ```

## 2. 注册 SSH key（可选，仅用于 git push 源码仓库）

1. 本机公钥：`~/.ssh/id_ed25519.pub`（指纹 `SHA256:3DYpb3CjolAlEhowCLiy0jhe6Iz14xuQ0v4/6LA4bhM`）。
2. 打开 <https://launchpad.net/~mymathersname-gmail/+editsshkeys>，粘贴公钥，Import。
3. 验证：
   ```bash
   ssh -o IdentitiesOnly=yes -i ~/.ssh/id_ed25519 git@git.launchpad.net
   ```
   **注意：git push 不会发布 deb；PPA 发布走 dput，不需要 SSH key。**

## 3. 创建 PPA 并启用 riscv64（必须在首次上传前）

1. 打开 <https://launchpad.net/~mymathersname-gmail/+activate-ppa>。
2. PPA 已创建；URL 名是 `ppa`，display name 是 `firefox-k3`。
3. 打开 <https://launchpad.net/~mymathersname-gmail/+archive/ubuntu/ppa/+edit>。
4. 在 **Processors** 勾选 `riscv64`，Save。
   - 这一步必须在 `dput` 之前；后补架构不会自动为已上传源码补 build。
   - 不需要签 Ubuntu CoC；账号 probationary 不影响 PPA 创建。

## 4. 上传源码包

确认第 1 步完成、第 3 步 riscv64 已勾选后：

```bash
cd /mnt/k3work/firefox-k3/ppa
dput ppa:mymathersname-gmail/ppa \
  firefox_160.0+build1-0ubuntu0.26.04.1~mt1k3.1_source.changes
```

上传内容：`.dsc`（已签）、`.debian.tar.xz`、`.orig.tar.xz`（790MB）、`.buildinfo`。
上传后 Launchpad 会为 `resolute/riscv64` 排队构建；riscv64 重包构建常以“一天”量级计。

## 验证下载/安装（构建成功后）

```bash
sudo add-apt-repository ppa:mymathersname-gmail/ppa
sudo apt update
sudo apt install firefox
```

> 注意：Ubuntu 26.04 的 `firefox` 是 snap 过渡包；本 PPA 提供的是真正的 deb
> （`firefox` 二进制包），安装前请确认 apt 选择的是 PPA 版本而不是 `1:1snap1`。
> 可用 `apt-cache policy firefox` 核对候选版本是否带 `~mt1k3.1`。

## 当前构建能力边界

- Phase 1（本上传包）：`clang-22` + `rustc-1.91` + `-march=...xsmtvdot`，即 RVV + IME1；
  PPA 档案内工具链，零自建工具链。`rustc-1.91` 是最后一个 host=`riscv64gc` 的档案版本。
- Phase 2（IME2）：需要先把最小 `clang-24` 工具链源码包传到同一个 PPA，再上传
  Firefox 的 `-march=...xsmtvdotii` 变体；Launchpad 上预估 1–3 天构建，成本高。
- 本地 IME2 构建（A100）另行交付；默认包应只带 IME1，避免 X100 上 SIGILL。

## 安全注意

- 不要把 `passphrase`、私钥、`.gnupg` 目录提交到 git 或发到聊天。
- 建议把 `ppa-signing-key.asc`、fingerprint、撤销证书备份到离线介质。
- 如果 key 泄露，立即用撤销证书吊销，并在 Launchpad 删除旧 key。
