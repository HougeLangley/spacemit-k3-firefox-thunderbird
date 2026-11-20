# SpacemiT K3 Firefox / Thunderbird

日期：2026-11-20（UTC）

Ubuntu 26.04 `riscv64` / SpacemiT K3 构建与 Linlon VPU 硬解交付。项目地址：
<https://github.com/HougeLangley/spacemit-k3-firefox-thunderbird>

## 本轮版本

| 组件 | 版本 | 主要用途 |
|---|---|---|
| MPP | `0.1.15+k3.8` | V4L2/MPP buffer 所有权、flush、EOS 与重复 NULL_DATA 修复 |
| FFmpeg | `7:8.0.1-3ubuntu2bb1k3.2` | `h264/hevc/vp8/vp9_stcodec`，flush 后不再丢弃十帧有效输出 |
| Firefox | `160.0+build1-0ubuntu0.26.04.1~mt1k3.9` | 系统 FFmpeg stcodec 硬解及 Wayland GLX 早退修复 |
| Thunderbird | `1:160.0-1k3.1` | 沿用此前已构建兼容包；**不是本轮重建或重新验收** |

Firefox k3.8 因虚拟 Wayland 下误选 FFVPX 被拒绝，所有产物和日志已隔离到
`rejected/`；本轮 Firefox 发布版本是新的 k3.9，不复用旧 pre-release 或旧 tag。

## 硬解实现，不做规避

K3 的 PowerVR `cac00000.imggpu` 与 Linlon `c0500000.linlon-v5` 是独立硬件。
Firefox 使用 `/dev/video0` 的 V4L2 M2M multiplanar 接口和系统 FFmpeg
`*_stcodec` 解码器，取得 CPU 可读的 planar I420，再复制到 Firefox YUV image。
这条路径不依赖 PowerVR OpenGL/Vulkan、EGL 或 DMABUF。

本轮没有全局关闭硬解，没有错误过滤 VP8/VP9，没有隐藏 MPP 日志，也没有把
FFVPX 软件播放当成硬解成功。AV1 没有对应 K3 stcodec，仍明确使用软件解码。

关键修复：

- MPP：串行化 flush/return；output-EOS latch；每个已出队的
  `OK/NULL_DATA/ERROR_FRAME` buffer 都明确转移所有权，防止 HEVC 重复
  NULL_DATA 后死锁；stale return 不再进入驱动。
- FFmpeg：保留 flush/EOS/resolution 的正常消息语义，移除后续 flush 无条件
  丢弃十帧有效输出的行为；真实错误仍保持 error 级别。
- Firefox：优先系统 FFmpeg 硬件 codec，严格处理 vendor plane 生命周期；
  在 RISC-V 的全局硬解和 per-codec 查询中，于 GLX 失败早退之前执行真实
  V4L2 能力判定，因此 Wayland 不再因 `FEATURE_FAILURE_GLXTEST_FAILED`
  错选 FFVPX。编码和 AV1 能力门禁没有被绕过。

详见 [MPP 研究](research/mpp-k38.md)与
[Firefox Wayland 根因](research/firefox-wayland.md)。

## 验收证据

### Native 三纪元循环矩阵

最终 MPP k3.8 + FFmpeg k3.2 对 H.264、HEVC、VP8、VP9 分别通过三次循环：

- 每次恰好 **1350 帧**，PTS 连续为 `0..1349`；
- 每纪元 450 个唯一 PTS/hash，三纪元 hash 完全一致；
- 正常退出、无超时、零 `MPP-ERROR`。

证据导出：`artifacts/validation/native-*-loop3.json`。

### 最终 Firefox k3.9 deb

| 场景 | 解码器 | 硬件帧日志 | VPU IRQ 增量 | MPP 错误 |
|---|---|---:|---:|---:|
| H.264 / Xvfb 15 秒 | `h264_stcodec` | 516 | 10389 | 0 |
| HEVC / Xvfb 15 秒 | `hevc_stcodec` | 515 | 11054 | 0 |
| VP8 / Xvfb 15 秒 | `vp8_stcodec` | 519 | 7583 | 0 |
| VP9 / Xvfb 15 秒 | `vp9_stcodec` | 522 | 11167 | 0 |
| H.264 / HTTP 45 秒 | `h264_stcodec` | 1417 | 29112 | 0 |
| VP9 / 虚拟 GNOME Wayland | `vp9_stcodec` | 525 | 11114 | 0 |

所有硬解场景均要求 `IsHardwareAccelerated=1`、严格 preference、真实
`*_stcodec`、无后续软件 decoder、每纪元 450 个连续硬件 PTS 和可测 VPU 活动。
HTTP 场景跨 4 次 `ProcessFlush` 验证时间戳纪元。

AV1 对照明确为 FFVPX/libdav1d 软件路径：150 帧推进、无 `av1_stcodec`、
零 MPP 错误。它没有冒充硬件成功。

证据导出：`artifacts/validation/`；构建机原始日志位于
`/mnt/k3work/firefox-k3/tests/mpp-hw/browser-k39-final/`。Xvfb 与虚拟 Wayland 的少量
presentation dropped frames 不被改写成 decoder frame loss；native framehash
矩阵单独证明解码完整性。虚拟 Wayland 使用 headless GNOME/Mutter 和
`/dev/dri/renderD128`，**不是物理显示器验证**。

## 构建与源码

- Firefox authoritative source：
  `/mnt/k3work/firefox-k3/release/firefox-160.0`
- C/C++：clang/lld 24，K3 RISC-V feature flags 保留。
- Rust：1.97；`+xsmtvdot` 因已复现的 LLVM scalarization ICE 保持排除，
  不伪称启用 IME。
- Firefox clean binary build 与 binary lintian error gate 已通过；最终安装版本由
  `dpkg-query` 和 `firefox --version` 回读。source lintian 的四个 orig 继承错误
  和临时索引 warning 未隐藏，详见 `STATUS.md`。
- MPP 与 FFmpeg 均通过最终 binary/source lintian 和独立 `.dsc` 解包后的
  binary roundtrip rebuild。

构建只使用 `clang-24` / GCC 17 工具链能力；不把编译参数等同于真实 IME kernel。

## 安装与权限

发布资产的 SHA-256 位于 `artifacts/SHA256SUMS`，安装前先执行
`sha256sum -c SHA256SUMS`。GitHub 会把 Firefox 下载文件名中的 `~` 规范化为
`.`；release 附带的远端 `SHA256SUMS` 已使用实际下载名，deb 内部版本与哈希不变。
本地包可用 `apt install ./<package>.deb` 安装；
FFmpeg 运行库应使用同一 k3.2 构建集合。PPA 目标是
`ppa:mymathersname-gmail/ppa`，是否能安装必须以 Launchpad 新版本的实际
`Published` 状态为准，不能由本地上传命令推断。

`/dev/video0` 保持 `root:video 0660`，没有添加 permissive udev 规则。运行硬解
的桌面用户必须属于 `video` 组。严格测试使用：

```text
media.hardware-video-decoding.enabled=true
media.hardware-video-decoding.force-enabled=true
media.ffmpeg.disable-software-fallback=true
```

不要把第三项用于普通 AV1 播放配置；AV1 对照由 harness 显式启用软件 codec。

## 公开补丁与凭据

公开补丁位于 `patches/`；旧的 `k3-v4l2-codec-filter.patch` 已不再使用。
仓库不保存 GitHub token、GPG 私钥或 passphrase。GitHub tag/release 和 PPA
上传/构建状态只在远端独立回读后更新到 STATUS.md。
