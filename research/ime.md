# Firefox / Thunderbird 在 SpacemiT K3 上使用 IME1/IME2 的最小可行落点评估

- 评估对象：Firefox 160.0（`/mnt/k3work/firefox-k3/build/firefox-160.0`）；Thunderbird 140.x（`sources/tb-debian`，1:140.17.0）与其共用 Gecko media/gfx 架构，结论按同源路径适用，具体行号需按 140 分支核对
- 评估方式：**只读**主源码树；所有微基准/原型验证都在 `/tmp` 完成，未修改 `build/`、`sources/`
- 日期：2026-11-14
- 结论先行：**（c）对浏览器热路径不划算**。若目标只是“证明 Firefox 能用上 IME2”，可在 `media/libjpeg` 做一个 opt-in 研究原型，但那是 **(b) 高成本研究项**，不是低风险可落地项。真正在 K3 上有可用性的是 **IME1 `vmadot`（X100/A100 都支持）**，不是 IME2 `vfwmadot`（仅 A100、VLEN=1024）。

---

## 0. 结论（TL;DR）

1. **IME2 `smt.vfwmadot` 在 K3 上只存在于 A100 簇**（cpu8–15，VLEN=1024，1.8 GHz）。X100 簇（cpu0–7，VLEN=256，2.15 GHz）执行 `vfwmadot` 直接 SIGILL。实测：
   - `cpu0 vlenb=32 smt.vfwmadot: SIGILL`
   - `cpu9 vlenb=128 smt.vfwmadot: 可执行，最大相对误差=0`
2. **IME1 `smt.vmadot` 在 X100 和 A100 都能执行**，分别得到 4×8×4（K=8）和 8×16×8（K=16）的 int8→int32 点积；对 8-bit 像素是精确的，对 16-bit 变换系数需要 limb 分解。
3. Firefox 没有任何现成 IME 集成：全树 grep `vfwmadot|vmadot|xsmtvdot`（C/C++/S）命中 0 次（`third_party/llama.cpp` 只有对 `spacemit/ime.h` 的引用，未见 vendored IME 内核源码）；`media/libjpeg` 在 riscv64 上是纯标量 C（libjpeg-turbo 3.1.4.1 无 RVV），`media/libwebp` 无 RISC-V SIMD，`media/ffvpx` 只有 x86 asm，dav1d 虽有 RISC-V RVV asm 但 Firefox 在 riscv64 上不编译它。
4. **结构上唯一真正匹配的是 libjpeg 的 8×8 IDCT**：二维 IDCT = 两次 8×8×8 矩阵乘，正好是 `vfwmadot` 的 tile。但实测/估算：
   - 标量 `_jpeg_idct_islow`：**328.9 ns/block**（X100，clang 24 -O2，实测）；
   - IME2 两 GEMM/块的简化流水线（含 pack/unpack、无转置/舍入）：**214.2 ns/block**（A100，实测）；
   - 上限仅 **1.54×**；加上 IDCT 必需的中间转置和整数舍入，现实约 **1.1–1.3×**。
   - 端到端 JPEG 解码即使按 IDCT 占 40% 估算，也只有 **<10–15%** 的收益，而且前提是**整个浏览器**都搬到 8 个 A100 核上。
5. 把整个 Firefox 绑到 A100 的代价：失去 8 个 2.15 GHz X100 核、只剩 8 个 1.8 GHz A100 核，整机浏览器吞吐净损失；正常启动时亲和性通常包含 0–15，线程可能落在 X100（`vlenb=32`）或 A100（`vlenb=128`），只要掩码里含 X100，IME2 探针就必须返回 false，否则一次迁移到 X100 就是 SIGILL。**没有“只用图像解码线程跑 IME2”的低成本办法**：`ai-run` 是 exec 级绑定，线程不能跨簇迁移。
6. 因此：
   - **生产落地（a）**：没有证据支持。
   - **1–2 天原型（b）**：可以做，但只在 `ai-run` + `MOZ_JPEG_IME2=1` 的 opt-in 条件下成立，且应默认关闭、默认回退；它的价值是拿到“值不值得继续”的判定数据，而不是上线。
   - **对浏览器热路径（c）**：IME2 不划算；若要做 K3 浏览器多媒体加速，优先级应是 **标准 RVV**（例如先把 pixman-rvv、dav1d RISC-V asm 接进 Firefox），而不是厂商 IME2。

---

## 1. 本机实测环境与证据

| 项 | 实测值 | 证据 |
|---|---|---|
| CPU 拓扑 | 8× X100（cpu0–7，2.15 GHz）+ 8× A100（cpu8–15，1.8 GHz） | `lscpu -e`、`/proc/cpuinfo`：`spacemit,x100` / `spacemit,a100` |
| 默认亲和性 | `0-7`（本 shell） | `/proc/self/status` `Cpus_allowed_list: 0-7` |
| A100 运行方式 | `ai-run <cmd>` → `Cpus_allowed_list: 8-15`，`vlenb=128` | `/usr/local/bin/ai-run` + `/tmp/aff` 实测 |
| X100 `vlenb` | 32（VLEN=256） | `csrr vlenb` |
| A100 `vlenb` | 128（VLEN=1024） | 同上 |
| `vfwmadot` on X100 | SIGILL | `/home/ubuntu/k3-ncnn/ime/ime_vfwmadot_verify`，cpu0–7 全部 SIGILL |
| `vfwmadot` on A100 | 可执行，随机 8×8 对拍最大相对误差 0 | 同上，`ai-run` 下 cpu9 |
| `vmadot` on X100 | 可执行；全 1 输入 C[0]=8（K=8，4×8×4） | `/tmp/vmadot_test`，抽测 cpu0/cpu4 |
| `vmadot` on A100 | 可执行；全 1 输入 C[0]=16（K=16，8×16×8） | 同上，`ai-run` |
| IME2 大 GEMM 吞吐 | 74.84 GFLOP/s（1024³×20，单核） | `ai-run /home/ubuntu/k3-ncnn/ime/ime2_gemm_fp16_2x2` |
| IME1 4 路吞吐 | 3.43 ns/instr，37.3 G-MAC/s（X100 单核） | `/tmp/ime1_tp` |
| IME1 单条延迟 | 12.53 ns/instr（1 路，未展开） | `/tmp/ime1_bench` |
| 标量 IDCT | 328.9 ns/block（X100，单核） | `/tmp/jpegbench/bench`（Firefox `jidctint.c` 原文件 + 最小 harness） |
| IME2 2-GEMM 块流水 | 214.2 ns/block（A100；pack 53.0 ns） | `/tmp/ime2_block_bench`（2×vfwmadot，无转置/舍入） |
| 工具链 | clang 24.0.0git，可用 `-march=rv64gcv_zba_zfh_zvfh_zicbop_xsmtvdot_xsmtvdotii` | `/mnt/k3work/firefox-k3/toolchain/bin/clang-24 --version` |
| LLVM 指令编码 | `vfwmadot` `[0x2b,0x48,0x81,0x9e]`；`vmadot i8` `[0x2b,0x31,0x10,0xe2]`；`vmadot i4` `[0x2b,0x31,0x10,0xc2]` | `llvm-mc -triple=riscv64 -mattr=+xsmtvdotii -show-encoding` |

> 说明：`ime_vfwmadot_verify` 与 ncnn 的 `ime2_probe()` 都以 `vlenb==128` 作为“当前线程在 A100 且 VLEN=1024”的判据；这不是随意的启发式，而是 `vfwmadot` 的 8×8×8 tile 需要 1024-bit VLEN（见 §2）。

---

## 2. K3 上 IME1/IME2 的实际语义（问题 3）

### 2.1 `vmadot` vs `vfwmadot`

| 维度 | IME1 `smt.vmadot` | IME2 `smt.vfwmadot` |
|---|---|---|
| 操作数 | `[U]Int8 × [U]Int8`（另有 `i4` 变体） | `FP16 × FP16`（或 BF16，由 `MCPM.BF16` 选择） |
| 累加器 | `Int32`，**精确** | `FP32`（输入只有 11-bit 尾数） |
| X100 / VLEN=256 | 4×8×4 tile，K=8，128 MAC/指令 | **不支持，SIGILL** |
| A100 / VLEN=1024 | 8×16×8 tile，K=16，1024 MAC/指令 | 8×8×8 tile，K=8，512 MAC/指令 |
| 目标寄存器 | `vd` 必须是偶数号，占 2 个向量寄存器（`MUL_C=2`） | 同左；`vd` 偶数号，2 个寄存器（`e32,m2`） |
| 输入寄存器 | `vs1`/`vs2` 各 1 个寄存器，`LMUL=1` | 同左；`vs1`/`vs2` 各 1 个寄存器 |
| 语义 | `C += A × B^T`（`B` 在寄存器里按列主序/几何转置存放） | `C += A × B^T` |
| 适合 8-bit 像素 | **是**（精确 int32） | 不是首选（要 float 转换） |
| 适合 16-bit 变换系数 | 需 16-bit 拆成高低 8-bit limb，3–4 倍指令 | 不适合 bit-exact：fp16 只有 11-bit 尾数 |

补充：
- `smt.vfwmadot1/2/3` 是滑动窗口变体（对 A 做 1/2/3 的固定偏移），面向卷积/FIR，不是 IDCT 需要的通用 8×8×8。
- `smt.vmadot.hp*` 是带块缩放的 int8 变体（fp16/BF16 scale + fp16/BF16 累加），面向量化 NN；`smt.vmadot.sp*` 是 4:2 结构化稀疏。它们都不是图像编解码的自然落点。
- 官方文档：A100 的 `Xsmti8i32mm` 为 8×16×8，`Xsmtfp16fp32mm` 为 8×8×8；`MUL_C=2`、`LMUL=1`、`vd` 偶数且不得与 `vs1/vs2` 重叠。见 [SpacemiT IME 文档](https://github.com/spacemit-com/docs-ai/blob/main/en/architecture/ime_extension.md)。
- LLVM 侧：`VFWMADOT` 的 `vd` 是 `VRM2`（2 个寄存器），`vs1` 是 `VR`，`vs2` 是 `VR`；`vmadot` 的 `vd` 是 `VRM2`，`vs1/vs2` 是 `VR`。见 [LLVM PR #202533](https://github.com/llvm/llvm-project/pull/202533) 与本地 `llvm-mc` 编码。

### 2.2 为什么“仅 A100”是硬约束

- `vfwmadot` 的 A 矩阵是 8×8 fp16 = 64×2 B = 128 B = 1024 bit，正好占满一个 VLEN=1024 的寄存器；X100 的 VLEN=256 装不下这个 tile，执行即非法指令。
- `ai-run` 的注释明确：注册到 A100 会把线程 VLEN 从 256 改成 1024；**已经跑过向量代码的线程再被搬运会破坏向量状态**。因此 IME2 只能“进程启动时就决定”，不能在一个已经运行的 Firefox 进程里动态启用/迁移。
- 这不是“加个 `-march` 就能用”的问题：编译进 IME2 指令后，任何一次在 X100 上的执行都是 SIGILL；浏览器线程调度不受库控制。

---

## 3. 候选落点对比（问题 1）

### 3.1 对比表

| 候选 | 位置/函数 | 结构匹配 | 输入/输出布局 | 精度风险 | 现状 | 预期收益 | 判定 |
|---|---|---|---|---|---|---|---|
| **libjpeg 8×8 IDCT** | `media/libjpeg/src/jidctint.c:173` `_jpeg_idct_islow`；`jddctmgr.c:167` 分派 | ★★★★★ 两次 8×8×8 GEMM | 输入 dequantized int32 `coef_block[64]`（行主序）；中间 int32 workspace；输出 8×8 uint8 + `range_limit` | **高**：fp16 只有 11-bit 尾数；实测 ±1023 系数最大误差 0.81 LSB；±260k 溢出为 inf/NaN | riscv64 纯标量 C（libjpeg-turbo 3.1.4.1 无 RVV） | 内核上限 1.54×；现实 1.1–1.3×；端到端 <10–15% | **唯一值得做原型，但不适合生产** |
| pixman blend | `gfx/pixman/pixman/pixman/pixman-rvv.c:3023` | ★ 逐像素 alpha 混合，非点积 | 8-bit 通道交织；每像素 3–4 次 8-bit 乘法 | 低（但需要 pack/unpack） | Firefox 只编译 `pixman-riscv.c`，**没有编译 `pixman-rvv.c`**；上游有 RVV 路径 | ≤1.0×（内存带宽瓶颈，pack 开销更大） | 不做 |
| pixman scale | pixman bilinear/卷积路径 | ★★ 2-tap/8-tap 可分离滤波；8-tap 才像点积 | 8-bit 像素 + 16-bit 定点系数 | 中（系数 16-bit，int8 量化有误差） | 同上；RVV 未接入 | ≤1.1×，且缩放不是最大热点 | 不做 |
| libwebp YUV→RGB | `media/libwebp/src/dsp/yuv.h:26` `VP8YuvToRgb`；`yuv.c:46` | ★★ 每像素 3 项；可拼成 4 像素 × RGB 的 4×4 输出（K=3 补到 8） | Y/U/V 三平面 8-bit；输出 RGB 交织 | 中：系数是 16-bit 定点（19077/26149/…），int8 化会掉精度；fp16 路径要转换 | 无 RISC-V SIMD；只有 SSE2/NEON/MIPS/MSA | ≤1.05×；1080p30 只有约 0.19 G-MAC/s，远低于内存带宽 | 不做 |
| dav1d ITX | `third_party/dav1d/src/riscv/64/itx.S`（上游 1.5.4 已有 RVV asm）；C 路径 `third_party/dav1d/src/itx_1d.c` | ★★★ 4×4/8×8/16×16 整数变换 | 16-bit 中间值；有符号 16-bit 系数 | 高：AV1 变换要求 16-bit 精确中间值 | Firefox 在 riscv64 上 **不编译 dav1d asm**（`toolkit/moz.configure:962` 只对 arm/aarch64/x86/x86_64 开）；C 路径可用 | 先把 RVV asm 接进来更划算；IME2 需要重写且难 bit-exact | 不做（优先级低于接 RVV） |
| ffvpx IDCT | `media/ffvpx/libavcodec/idctdsp.c:286` `ff_simple_idct_int16_8bit` | ★★★ 8×8 整数 IDCT | int16 系数/中间值；输出 8-bit | 高（16-bit 精确） | 只有 x86 asm；riscv64 纯 C | 同 JPEG，但 ffvpx 的 IDCT 只是解码一环 | 不做 |
| 音频重采样 | `media/libspeex_resampler/src/resample.c:367` `inner_product_single` | ★★ 8/16-tap FIR，天然点积 | float 样本（`FLOATING_POINT=True`）；8/16 tap | 中：fp16 转换有误差；但音频对 1 LSB 不敏感 | riscv64 无 SIMD，纯 C | 48 kHz 立体声约 1.5 M-MAC/s，**<0.1% 整机** | 不做 |

### 3.2 为什么 IDCT 是“结构上唯一匹配”

libjpeg 的 8×8 IDCT 是二维可分离变换：

```
Z = M · X · M^T
```

其中 `X` 是 dequantized 系数块，`M[n][k] = c(k)·cos(π(2n+1)k/16)` 是 8×8 IDCT 基矩阵。`vfwmadot` 计算 `C = A·B^T`，所以：

- 第一遍：`Y = X·M^T`（A=`X`，B=`M`），一次 8×8×8；
- 第二遍：`Z = M·Y`；由于 `M` 不对称，必须写成 `Z^T = Y^T·M^T`（A=`Y^T`，B=`M`），再转置输出；
- 每块 2 条 `vfwmadot`（K=8 时每条 512 MAC），外加**一次 8×8 转置**、fp32→fp16 转换、整数舍入/饱和。

这正好解释了为什么“理论算力很漂亮、实测一般”：`vfwmadot` 的 512 MAC 只要 ~13.7 ns（按 74.8 GFLOP/s），但每块的 pack、转置、舍入是标量工作，无法被矩阵单元吸收。

### 3.3 实测拆解（关键数字）

| 步骤 | 实测/估算 |
|---|---|
| 标量 `_jpeg_idct_islow` 整块 | **328.9 ns/block**（X100，2.15 GHz，clang 24 -O2，200k 次） |
| IME2 pack（64×int32→fp16） | **53.0 ns/block**（A100） |
| IME2 2×vfwmadot + 2 次 load/store + 64×float→uint8 | **214.2 ns/block**（A100，简化流水，无转置/舍入） |
| 真实 IDCT 需要的额外转置/舍入 | 估算 +50–100 ns/block |
| 现实 IME2 整块 | **约 260–310 ns/block** |
| 相对标量 | **1.1–1.3×**（不是 1.54×；1.54× 是未计转置的上限） |

> 注：标量 IDCT 对“AC 全零列”有短路（`jidctint.c:195` 附近），真实 JPEG 的标量耗时通常低于 328.9 ns；因此 IME2 的相对优势只会更小。

### 3.4 精度实测

用理想 8×8 DCT 基矩阵模拟“输入/中间值都转 fp16、fp32 累加”的 IDCT，50 个随机块：

| 系数范围 | 最大绝对误差（像素） | 说明 |
|---|---|---|
| ±64（典型 q=16） | 0.053 | 基本安全 |
| ±1023（高质量 q=1） | **0.810** | 四舍五入后可能差 1 LSB；不保证 bit-exact |
| ±260000（极端 dequant） | **NaN/Inf** | fp16 溢出；必须逐块检查并回退 |

结论：IME2 IDCT **不能保证与 libjpeg 标量路径逐像素一致**。Firefox 的 JPEG reftest/解码测试会比对参考输出（允许容差需按具体测试套件确认）；要做生产路径，必须要么接受“显示专用、canvas 走标量”的双路径，要么做 16-bit limb 分解（见 §3.5），那就不是 1–2 天的事了。

### 3.5 如果一定要在 K3 上做整数精确 IDCT：IME1 是另一条路

- `vmadot` 在 X100 上可用（4×8×4，K=8），int32 累加**精确**；对 16-bit 系数做 `x = xh·256 + xl` 分解，两个 16-bit 数相乘需要 3–4 个 int8 点积（Karatsuba 可降到 3 个）。
- 8×8 输出需要 4 个 4×4 象限；一次 8×8×8 等价于 4 条 `vmadot`，再乘 3–4 个 limb 乘积 → **每 GEMM 12–16 条，每块 24–32 条**。
- 实测 4 路吞吐 3.43 ns/instr → **82–110 ns/block** 的矩阵时间；加上 pack/limb 拆分/转置，估算 180–280 ns/block，相对 328.9 ns 只有 1.2–1.8×，且代码复杂度远高于 IME2。
- 这是“可能的后续研究项”，不是本轮 1–2 天能闭环的方案；且它用的是 IME1，不是 IME2。

---

## 4. 1–2 天原型补丁方案（问题 2，不直接改源码树）

> 目标：用最小改动验证“IME2 IDCT 在真实 Firefox 解码路径里是否可能 ≥1.3× 且不破坏正确性”。**默认关闭、默认回退、只在 `ai-run` + `MOZ_JPEG_IME2=1` 下启用。**
> 前置条件：已有一个能增量编译的 Firefox 160 构建；编译器为 clang 24（或 GCC 17）且支持 `xsmtvdotii`。本机当前只有 `toolchain/bin/clang-24`，未做全量构建。

### 4.1 文件与函数

| 文件 | 改动 |
|---|---|
| `media/libjpeg/src/riscv/jidctint_ime2.h`（新增） | 声明 `int moz_jpeg_ime2_available(void);` 与 `void moz_jpeg_idct_islow_ime2(j_decompress_ptr, jpeg_component_info *, JCOEFPTR, JSAMPARRAY, JDIMENSION);` |
| `media/libjpeg/src/riscv/jidctint_ime2.c`（新增） | 探针 + 8×8 IDCT 内核（内联 asm） |
| `media/libjpeg/src/jddctmgr.c` | 在 `JDCT_ISLOW` 分支（`jddctmgr.c:167`）前加 `#ifdef MOZ_JPEG_IME2` 的 opt-in 分派 |
| `media/libjpeg/moz.build` | `if CONFIG['TARGET_CPU'] == 'riscv64':` 加源文件、`DEFINES['MOZ_JPEG_IME2']=True`、per-file flags |
| `modules/libpref/init/StaticPrefList.yaml`（可选） | 用 pref 代替环境变量；原型阶段环境变量更快 |

### 4.2 内核数据布局与伪代码

```
输入: coef[64] int32 (dequantized, 行主序), quant table, range_limit
常量: M[64] fp16 (IDCT 基矩阵, 预打包为 vfwmadot 的 B tile, 列主序)
每块:
  1) 检查 max|coef| <= 2048；否则 return 0 -> 标量回退
  2) pack_coef_to_tile: 64 × (int32 -> fp16), 行主序写入 A_tile[64]（128 B）
  3) vfwmadot C1 = A_tile × M^T        // Y = X·M^T
  4) 对 C1 做 descale/round，转置写入 A2_tile[64] fp16
  5) vfwmadot C2 = A2_tile × M^T       // Z^T = Y^T·M^T
  6) 对 C2 做 descale、range_limit、写 8×8 uint8 输出（按转置索引）
```

内联 asm 约束（与 ncnn/官方示例一致）：

```c
// A/B 各 128 B，C 为 2 个寄存器（e32,m2）
vsetvli t0, zero, e16, m1, tu, mu
vle16.v v2, (A)
vle16.v v8, (B)
vsetvli t0, zero, e32, m2, tu, mu
vmv.v.i v16, 0
vsetvli t0, zero, e16, m1, tu, mu
smt.vfwmadot v16, v2, v8
vsetvli t0, zero, e32, m2, tu, mu
vse32.v v16, (C)
```

硬约束：
- `vd` 必须是偶数号（`v16` 可以，`v17` 是它的高 half），且不得与 `vs1/vs2` 重叠；
- 执行 `vfwmadot` 时 `vtype` 必须是 `e16,m1`（不是 `e32,m2`）；清零/存储时切到 `e32,m2`；
- `LMUL=1`；A/B 必须是连续的 8×8 fp16 tile（行主序），B 在寄存器里是“几何转置”布局；
- 编译器必须开 `-march=...xsmtvdotii`，否则汇编器报 `unrecognized opcode`（实测 clang 24 可接受）；
- 不要把 `vfwmadot` 放在会被 X100 执行的函数里；整个函数必须受 §4.3 的探针门控。

### 4.3 运行时 CPU 探测（关键安全门）

```c
static int probe_once(void) {
    static int cached = -1;
    if (cached >= 0) return cached;
    cached = 0;

    // 1) 亲和性必须严格落在 A100 簇 8..15；只要包含 0..7 就拒绝
    cpu_set_t set;
    if (sched_getaffinity(0, sizeof set, &set) != 0) return 0;
    for (int c = 0; c < 8; c++) if (CPU_ISSET(c, &set)) return 0;
    int has_a100 = 0;
    for (int c = 8; c < 16; c++) if (CPU_ISSET(c, &set)) has_a100 = 1;
    if (!has_a100) return 0;

    // 2) VLEN 必须是 1024（ai-run 已把线程注册到 A100）
    unsigned long vlenb = 0;
    __asm__ volatile("csrr %0, vlenb" : "=r"(vlenb));
    if (vlenb != 128) return 0;

    // 3) 一次性 SIGILL 探针（仅在启动早期、单线程时执行）
    //    用 sigsetjmp/sigaction 包住一条 vfwmadot；失败则返回 0。
    //    生产环境可省略第 3 步：亲和性 + vlenb 已足够强，避免在浏览器里装 SIGILL handler。
    cached = 1;
    return cached;
}

int moz_jpeg_ime2_available(void) {
    if (!getenv("MOZ_JPEG_IME2")) return 0;   // 原型阶段默认关闭
    return probe_once();
}
```

**回退路径**：`jddctmgr.c` 只在 `moz_jpeg_ime2_available()` 为真时替换 `method_ptr`；内核内部对每块做 `max|coef|` 检查，超阈值直接调用标量 `_jpeg_idct_islow`（函数指针回退）。任何异常/不支持都走原路径。

**为什么不能用“每次调用 `sched_getcpu()` 检查”**：检查与执行之间线程可能被迁移；只有“亲和性掩码 ⊆ 8..15”才能排除迁移到 X100 的可能。`ai-run` 已实测会把 `Cpus_allowed_list` 设为 `8-15`，所以这个门是可行的。

### 4.4 构建改动（moz.build 片段）

```python
if CONFIG['TARGET_CPU'] == 'riscv64':
    DEFINES['MOZ_JPEG_IME2'] = True
    SOURCES += [
        'src/riscv/jidctint_ime2.c',
    ]
    SOURCES['src/riscv/jidctint_ime2.c'].flags += [
        '-march=rv64gcv_zba_zfh_zvfh_zicbop_xsmtvdot_xsmtvdotii',
        '-mtune=spacemit-a100',
        '-fno-stack-protector',
    ]
```

- `SOURCES['file'].flags += [...]` 在 Firefox 树内有先例（`toolkit/crashreporter/test/moz.build:40` 等），可行。
- 只有这一个文件带 `_xsmtvdotii`；不要把它加到全局 `CFLAGS`，否则整个 libxul 都可能生成 IME 指令，在 X100 上 SIGILL。
- 现有 `media/libpng/moz.build:85` 的 RISC-V RVV 接入（`MOZ_PNG_USE_RISCV_RVV` + `riscv/filter_rvv_intrinsics.c`）是 Firefox 内最接近的模板；但 IME2 还需要 per-file `-march` 和亲和性门控，不能照抄。

### 4.5 单元测试与基准

**正确性**
1. 用 Firefox 的 JPEG reftest 语料（`image/test/reftest/jpeg`）+ 额外 100 张 4:2:0/4:4:4、q=1/50/95 的 JPEG；
2. 同一输入分别跑 `MOZ_JPEG_IME2=0/1`，比较 RGBA 输出：要求 `max diff == 0`（首选）或 `<= 1`（需产品/测试负责人签字）；出现 NaN/Inf 直接判失败；
3. 边界：全零 AC、DC only、最大 dequant（quant=255, coef=±1023）、渐进式 JPEG、灰度/CMYK。

**性能**
1. 微基准：单块 `ns/block`，对比 328.9 ns（X100 标量）与 IME2（A100）；
2. 端到端：`perf stat -e task-clock,cycles,instructions` 跑 20 张 4K JPEG 的本地页面；
   - 基线 A：正常启动（系统 cpuset 允许 0–15；本会话 shell 被限制在 0–7，实测时需说明）；
   - 基线 B：`ai-run` + `MOZ_JPEG_IME2=0`（8×A100，标量）——排除“换簇”影响；
   - 实验 C：`ai-run` + `MOZ_JPEG_IME2=1`（8×A100，IME2）；
   - 只有 **C 相对 B ≥10%** 且 **C 不慢于 A** 才算过关；否则结论是“内核快、产品不划算”。

**验收门槛**
- 探针：正常启动返回 false；`ai-run` 下返回 true；
- 正确性：max diff ≤1，无 NaN/Inf；
- 性能：单块 ≥1.3×，端到端（C vs B）≥10%；
- 稳定性：30 分钟压力/迁移测试无 SIGILL；
- 任何一项不过 → 停止，不进入生产补丁。

### 4.6 两天日程

| 天 | 任务 | 产出 |
|---|---|---|
| Day 1 上午 | 用独立 harness 复现 `/tmp/ime2_block_bench` 和 `/tmp/jpegbench/bench`；确认 clang 24 flags 与 A100 亲和性 | 基线数字、可重复脚本 |
| Day 1 下午 | 写 `jidctint_ime2.c`（先不接 Firefox），对拍标量 IDCT；测 100 张图的 max diff | 内核正确性/性能报告 |
| Day 2 上午 | 接 `jddctmgr.c` + `moz.build`，增量编译；跑 reftest | 可运行的 opt-in 补丁 |
| Day 2 下午 | 端到端 A/B/C 基准；写结论；若不过阈值，回滚并记录负结果 | 基准报告 + 决策 |

---

## 5. 风险清单

| 风险 | 级别 | 说明 | 缓解 |
|---|---|---|---|
| **SIGILL / 簇不对称** | P0 | `vfwmadot` 仅 A100；正常 Firefox 会在 X100 上执行 → 崩溃 | 亲和性 ⊆ 8–15 + `vlenb==128` 双门控；默认关闭；只允许 `ai-run` 启动 |
| **VLEN 状态损坏** | P0 | `ai-run` 注释：已跑向量代码的线程再注册到 A100 会破坏向量状态 | 只在进程 exec 前注册；不在运行中切换；不尝试“运行时迁移” |
| **精度不达 bit-exact** | P1 | fp16 尾数 11 bit；±1023 系数最大 0.81 LSB；±260k 溢出 | 逐块阈值回退；canvas/导出走标量；reftest 允许 ≤1 需签字 |
| **性能不达预期** | P1 | 214 ns 是不含转置的上限；真实 260–310 ns；1.1–1.3× | 先做独立 harness，达不到 1.3× 就停止，不接 Firefox |
| **整机吞吐下降** | P1 | 绑 A100 后失去 8×2.15 GHz X100，只剩 8×1.8 GHz A100 | 端到端 A/B/C 对比；若 C 不优于 A 则不产品化 |
| **构建/工具链** | P1 | 只有 clang 24/GCC 17 支持 `xsmtvdotii`；Firefox 构建可能未用该工具链 | per-file flags；CI 无 K3 硬件，需自建 runner；保留标量路径 |
| **厂商扩展无上游保证** | P2 | `xsmtvdotii` 是 vendor 扩展，LLVM 支持较新（PR #202533），编码/语义可能变 | 只在一个文件隔离；加编译期/运行期双重检测；文档记录版本 |
| **信号处理器安全** | P2 | 在浏览器里装 SIGILL handler 有风险 | 生产路径不用 SIGILL 探针；用亲和性 + vlenb；探针只在启动早期单线程执行 |
| **维护成本** | P2 | 厂商 asm + 特定簇逻辑，长期无人维护会成为负担 | 默认关闭、实验性 pref；不进入 stable 默认路径 |

---

## 6. 基准计划（可执行清单）

### 6.1 微基准（不依赖 Firefox）

```bash
# 1) 标量 IDCT（X100）
taskset -c 0 /tmp/jpegbench/bench
# 期望: idct_islow: ~329 ns/block

# 2) IME2 块流水（A100）
ai-run /tmp/ime2_block_bench
# 期望: pack ~53 ns/block, full ~214 ns/block

# 3) IME2 大 GEMM（A100）
ai-run /home/ubuntu/k3-ncnn/ime/ime2_gemm_fp16_2x2
# 期望: ~74.8 GFLOP/s（单核）

# 4) IME1 vmadot 吞吐（X100）
taskset -c 0 /tmp/ime1_tp
# 期望: ~3.43 ns/instr, ~37.3 G-MAC/s
```

### 6.2 端到端（接 Firefox 后）

| 组 | 启动方式 | 说明 |
|---|---|---|
| A（产品基线） | 正常启动 | 系统 cpuset 允许 0–15（本会话 shell 为 0–7）；标量 |
| B（换簇基线） | `ai-run` + `MOZ_JPEG_IME2=0` | 8×A100，标量；排除“换簇”影响 |
| C（实验） | `ai-run` + `MOZ_JPEG_IME2=1` | 8×A100，IME2 |

指标：页面加载时间、JPEG 解码 wall time、`task-clock`、`cycles`、`instructions`、每块 ns、max diff。
判定：C 相对 B ≥10%，且 C 不慢于 A；否则记负结果。

### 6.3 建议的样本

- 1080p 4:2:0 q=50/85 各 20 张；4K q=85 5 张；渐进式 5 张；灰度 5 张；
- 含大量 AC 零列（典型照片）和 AC 全非零（合成图）各一半，避免只测理想情况。

---

## 7. 外部补丁调查（问题 4）

| 项目 | 是否已有 SpacemiT IME2 补丁 | 证据/链接 | 可移植性判断 |
|---|---|---|---|
| **ncnn** | **有**（本地） | `src/layer/riscv/gemm_riscv_ime2.h`：`ime2_probe()` 要求 `vlenb==128`；8×8 tile 打包；`smt.vfwmadot` 内联 asm；实测 74.84 GFLOP/s | 只适用于 GEMM（`transB=1`），不能直接用于 IDCT；其 `probe` 与 tile 打包可复用 |
| **llama.cpp / ggml** | **有** | [PR #22863](https://github.com/ggml-org/llama.cpp/pull/22863) SpacemiT backend；[PR #32194](https://github.com/ggml-org/llama.cpp/pull/32194) 用 `vfwmadot` 做 flash-attention；本地 `ggml/src/ggml-cpu/spacemit/ime2_kernels.cpp` 使用 `smt.vmadot*` + `smt.vpack.vv` | 面向量化 GEMM/Attention，数据布局与图像块不兼容 |
| **MNN** | **有** | `source/backend/cpu/riscv/spacemit_ime2/`；`MNN_USE_SPACEMIT_IME2`、`_xsmtvdotii`、`-fno-stack-protector`；[K3 IME2 性能文档](https://github.com/alibaba/mnn/blob/c4d39887a7895669145f3a9cedef3088fb10b815/docs/perf/riscv_k3_ime2_asymmetric_w4b64.md) | LLM 专用；其工程约束（单独 object lib、只对该 lib 开 vendor ISA）值得借鉴 |
| **Bianbu / Chromium** | **未发现公开补丁** | Bianbu 2.0 发布说明只提到 Chromium 视频崩溃/长时间播放修复，未提 IME2；公开 GitHub 未检索到 `vfwmadot`/`vmadot` 的 Chromium 补丁 | Bianbu 可能带闭源 Chromium 优化，但无公开源码可验证；不能作为可移植实现 |
| **Skia** | **未发现** | Skia 的 RISC-V 支持是通用 RVV；Flutter RISC-V 社区移植只有 fontconfig 等补丁，无 IME2 | 无 |
| **FFmpeg** | **未发现公开 IME2 补丁** | Rémi Denis-Courmont 的 XSTIME/H.264 IDCT 实验是**负结果**：16-bit 元素模式有系统性算术错误，H.264 IDCT 无法加速；8-bit 模式才可用。见 [Remlab](https://www.remlab.net/op/riscv-xstime.shtml) | 与我们的精度分析一致：16-bit 变换系数不适合 IME |
| **libjpeg-turbo** | **无** | 3.1.4.1 在 riscv64 上 **没有 RVV 支持**（FreeBSD ports 的上游修复说明：`WITH_SIMD` 默认开但检测不到支持）。见 [FreeBSD commit](https://github.com/FreeBSD/freebsd-ports/commit/ef24c3da9913364ad643726375eda31b441c4f22) | Firefox 的 JPEG IDCT 仍是标量 C，是“有优化空间”的证明，但不是 IME2 的证明 |
| **libwebp** | **无** | `media/libwebp/src/dsp/` 只有 SSE2/SSE4/NEON/MIPS/MSA；无 RISC-V SIMD，更无 IME2 | 无 |
| **dav1d** | **有 RISC-V RVV asm，无 IME2** | `third_party/dav1d/src/riscv/64/itx.S` 等（上游 1.5.4）；Firefox 在 riscv64 上不编译（`toolkit/moz.configure:962`） | 接 RVV asm 比写 IME2 更划算；IME2 需要 bit-exact 的 16-bit 变换，风险高 |

**结论**：IME2 的公开使用者集中在 **NN 推理栈（ncnn/llama.cpp/MNN）**；浏览器/图像编解码栈没有公开的 IME2 补丁。这不是偶然——IME2 是 GEMM 指令，而浏览器热路径是逐像素/逐块的窄向量运算。

---

## 8. 最终建议（问题 5）

### 8.1 判定

**（c）对浏览器热路径不划算**，证据：

1. **硬件约束**：`vfwmadot` 仅 A100（8 核、1.8 GHz、VLEN=1024）；X100（8 核、2.15 GHz、VLEN=256）SIGILL。Firefox 正常进程不能安全使用它。
2. **进程绑定代价**：要用 IME2 必须 `ai-run` 整体绑到 A100；失去 8 个更快的 X100 核，整机浏览器吞吐下降。Firefox/Thunderbird 没有“只把图像解码线程放 A100”的现成机制。
3. **内核收益有限**：唯一结构匹配的 8×8 IDCT，实测简化流水 214 ns/block vs 标量 329 ns/block；加转置/舍入后现实 1.1–1.3×；端到端 <10–15%。
4. **精度风险**：fp16 11-bit 尾数，±1023 系数最大 0.81 LSB 误差，±260k 溢出；无法保证 bit-exact，reftest 难过。
5. **无先例**：Chromium/Skia/FFmpeg/libjpeg-turbo/libwebp 均无公开 IME2 补丁；唯一的公开实验（Remlab 的 XSTIME/H.264 IDCT）是负结果。

### 8.2 如果仍要推进

- **只做研究原型（b）**：按 §4 在 `media/libjpeg` 加 opt-in 内核，默认关闭；用 §6 的 A/B/C 基准拿到“是否 ≥10%”的硬数据；不满足就记录负结果并停止。
- **真正的产品优化优先级**：
  1. 先把 **标准 RVV** 接进 Firefox 的媒体路径：`pixman-rvv.c`（当前未编译）、dav1d RISC-V asm（当前未编译）、libpng RVV 已有先例；
  2. 如果目标是本地 LLM/WebNN，走 llama.cpp/MNN 的 IME2 路径，而不是图像解码；
  3. 如果目标是 IME1，优先评估 `vmadot` 在 X100 上的整数 IDCT（16-bit limb 分解），但那是独立的多周研究项。
- **Thunderbird**：与 Firefox 共用 Gecko media/gfx 栈，上述结论完全适用；邮件图片尺寸更小，ROI 更低，不建议单独投入。

---

## 附录 A：复现命令

```bash
# 环境
lscpu -e
cat /proc/self/status | grep Cpus_allowed_list
ai-run bash -c 'grep Cpus_allowed_list /proc/self/status; /tmp/aff'

# IME2 语义（X100 SIGILL / A100 OK）
taskset -c 0 /home/ubuntu/k3-ncnn/ime/ime_vfwmadot_verify
ai-run /home/ubuntu/k3-ncnn/ime/ime_vfwmadot_verify

# IME1 语义（X100 4x8x4 / A100 8x16x8）
taskset -c 0 /tmp/vmadot_test
ai-run /tmp/vmadot_test

# 吞吐
ai-run /home/ubuntu/k3-ncnn/ime/ime2_gemm_fp16_2x2
taskset -c 0 /tmp/ime1_tp

# 标量 IDCT / IME2 块流水
taskset -c 0 /tmp/jpegbench/bench
ai-run /tmp/ime2_block_bench

# LLVM 编码
echo 'smt.vfwmadot v16, v2, v8' | /mnt/k3work/llvm-build/bin/llvm-mc -triple=riscv64 -mattr=+xsmtvdotii -show-encoding
echo 'smt.vmadot v2, v0, v1, i8' | /mnt/k3work/llvm-build/bin/llvm-mc -triple=riscv64 -mattr=+xsmtvdotii -show-encoding
```

## 附录 B：关键源码位置

| 文件 | 行 | 内容 |
|---|---|---|
| `media/libjpeg/src/jidctint.c` | 173 | `_jpeg_idct_islow` |
| `media/libjpeg/src/jidctint.c` | 103/107 | `CONST_BITS=13` / `PASS1_BITS=1` |
| `media/libjpeg/src/jddctmgr.c` | 167 | `JDCT_ISLOW` 分派到 `_jpeg_idct_islow` |
| `media/libjpeg/moz.build` | — | libjpeg 源列表；riscv64 无 SIMD |
| `media/libjpeg/libjpeg-config.mozbuild` | — | `MOZ_WITH_SIMD` 只在有 SIMD flags 时定义 |
| `gfx/pixman/pixman/pixman/moz.build` | 36 | 只编译 `pixman-riscv.c`，未编译 `pixman-rvv.c` |
| `gfx/pixman/pixman/pixman/pixman-rvv.c` | 3023 | RVV fast paths（Firefox 未启用） |
| `media/libwebp/src/dsp/yuv.h` | 26–28 | YUV→RGB 16-bit 定点系数 |
| `media/libwebp/src/dsp/yuv.c` | 46 | `YuvToRgbRow` 等 |
| `media/libspeex_resampler/src/resample.c` | 367 | `inner_product_single` |
| `media/ffvpx/libavcodec/idctdsp.c` | 286 | `ff_simple_idct_int16_8bit` |
| `toolkit/moz.configure` | 962–973 | dav1d asm 只在 arm/aarch64/x86/x86_64 开 |
| `third_party/dav1d/src/riscv/64/itx.S` | — | 上游 RISC-V RVV ITX（Firefox 未编译） |
| `media/libpng/moz.build` | 85–90 | Firefox 已有的 RISC-V RVV 接入模板 |
| `media/libpng/riscv/riscv_init.c` | — | libpng RVV 运行时分派（标准 RVV，非 IME） |

## 附录 C：参考链接

- SpacemiT IME 指令集文档：<https://github.com/spacemit-com/docs-ai/blob/main/en/architecture/ime_extension.md>
- LLVM RISC-V `xsmtvdot`/`xsmtvdotii` 支持 PR：<https://github.com/llvm/llvm-project/pull/202533>
- Remlab（Rémi Denis-Courmont）XSTIME/H.264 IDCT 负结果：<https://www.remlab.net/op/riscv-xstime.shtml>
- llama.cpp SpacemiT backend PR：<https://github.com/ggml-org/llama.cpp/pull/22863>
- llama.cpp IME2 flash-attention PR：<https://github.com/ggml-org/llama.cpp/pull/32194>
- MNN K3 IME2 文档：<https://github.com/alibaba/mnn/blob/c4d39887a7895669145f3a9cedef3088fb10b815/docs/perf/riscv_k3_ime2_asymmetric_w4b64.md>
- MNN RISC-V kernel 规范：<https://github.com/alibaba/mnn/blob/24563667d4c923a6f67591a0132141a84b1e2ebb/skills/cpu/kernel/arch/riscv.md>
- FreeBSD libjpeg-turbo riscv64 修复（无 RVV）：<https://github.com/FreeBSD/freebsd-ports/commit/ef24c3da9913364ad643726375eda31b441c4f22>
- Bianbu 2.0 发布说明：<https://github.com/spacemit-com/docs-bianbu/blob/c835e3f3894ea740e6ca567e031b083131ce5674/en/release_notes/history/bianbu_2.0.md>
