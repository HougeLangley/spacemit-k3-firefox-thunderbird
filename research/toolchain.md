# Firefox/Thunderbird 带 IME2 的 PPA 工具链打包方案（riscv64 / Ubuntu 26.04）

- 调研日期：2026-11-14
- 性质：**只读调研**。未安装、未编译、未上传；未修改 `build/` 与 `sources/`。
- 目标：回答“Launchpad PPA 里构建带 IME2 的 Firefox/Thunderbird，工具链怎么落地”。
- 结论口径：Launchpad PPA 只收源码包；PPA 默认构建环境 = Ubuntu 档案 + 本 PPA，但**可以手动添加其他 PPA/档案作为构建依赖**（见 §4.5，任务给出的“PPA 不能依赖其他 PPA”不成立）。

---

## 0. 结论（先看这个）

1. **没有现成的 riscv64 clang-24 可以直接当 PPA Build-Depends。** apt.llvm.org 只发 `amd64/i386/s390x/arm64`，riscv64 索引 404；Ubuntu 26.04 档案最高只有 clang-22；Debian experimental 的 llvm-24 只有 amd64/arm64，riscv64 无包；Launchpad 上搜不到 `clang-24`/`llvm-24` PPA。
2. **PPA 原生支持 riscv64 构建，但不是默认架构。** 需要在 PPA 的 Processors 里启用 riscv64 并手动 Request builds；`karljs/llvm-22-symbols` 已有 riscv64 成功构建，证明可行。
3. **Debian 全量 llvm-toolchain 包在 Launchpad riscv64 上不可接受：** 实测整包构建 **198 小时（8 天 7 小时）/ 33.1 GB（31.6 GiB）构建空间**（Ubuntu 档案 llvm-toolchain-22），PPA 里同类构建 **258 小时（10 天 19 小时）**。这不是“能不能完成”，是“迭代成本不可接受”。
4. **如果 IME2 必须进 PPA，唯一干净路线是自带一个“最小 llvm-toolchain-24 源码包”**：只做 `RISCV` 后端 + `clang;lld`，单阶段 Release，不做 tests/docs/runtimes/compiler-rt/libcxx/lldb/mlir/flang。本机 8 核 riscv64 上仅 clang 主体就用了 **2 小时 00 分 53 秒**；最小包预估本机 3–5 小时、Launchpad 1–3 天（需实测，不能保证）。
5. **rustc 不需要自建。** 档案 rustc-1.97 动态链接 `libLLVM.so.22.1`，target-feature 只有 `xsmtvdot`（IME1），没有 `xsmtvdotii`（IME2）；自建 rustc 的实测成本是 **33.9 小时 CPU / 41.7 GB 构建空间**（还是链 LLVM 22 的版本），为 IME2 重建 rustc 性价比极低。IME2 只应放在 C/C++ 编译单元，Rust 侧不要加 `+xsmtvdotii`。
6. **推荐分两阶段：** 先走 (d) PPA 只做 IME1/RVV（用档案 clang-22，零工具链打包），把 PPA 交付跑通；IME2 作为 Phase 2，用最小 clang-24 源码包。不要打包 GCC 17，不要把预编译 clang 塞进 Firefox tar。

---

## 1. 证据与事实基线

### 1.1 本机 LLVM 24 源与本地工具链

| 项 | 值 | 证据 |
|---|---|---|
| LLVM 源版本 | 24.0.0（`LLVM_VERSION_SUFFIX=git`） | `/mnt/k3work/llvm-src/cmake/Modules/LLVMVersion.cmake`：MAJOR=24, MINOR=0, PATCH=0, SUFFIX=git |
| commit | `f59949b688b508821402adc5d69b26811a777fc6`，2026-10-05 | `git -C /mnt/k3work/llvm-src log -1 --format='%H %cd'` |
| 本地 clang | `clang version 24.0.0git (... f59949b...)`，Target `riscv64-unknown-linux-gnu` | `/mnt/k3work/llvm-build/bin/clang --version` |
| 本地构建 | `Release`，`LLVM_TARGETS_TO_BUILD=RISCV`，`LLVM_ENABLE_PROJECTS=clang`，只构建 `clang` 与 `llvm-mc` 两个 target | `/mnt/k3work/build_llvm.sh`；`llvm-build/CMakeCache.txt` |
| 本地构建耗时 | 2026-10-05 16:07:33 开始，18:08:26 产出 clang-24 → **2h00m53s** | `stat` 文件 mtime：`build_llvm.sh` 16:07:33、`llvm_cmake.log` 16:08:02、`llvm-build/bin/clang-24` 18:08:26 |
| 本地构建磁盘 | 构建目录 **1.7 GB**；源码树 **3.1 GB**（`.git` 359 MB、`llvm/` 1.6 GB、`clang/` 495 MB、`lld/` 25 MB、`cmake/` 92 KB、`third-party/` 14 MB） | `du -sh` |
| 本机资源 | 8 核，31 GB 内存，`/mnt/k3work` 剩余 149 GB | `nproc; free -g; df -h /mnt/k3work` |

**本地 IME2 证据（编译器侧）：**

```text
$ /mnt/k3work/llvm-build/bin/clang --print-supported-extensions | grep smtvdot
    xsmtvdot             1.0       'XSMTVDot' (SpacemiT Vector Dot Product Extension)
    xsmtvdotii           1.0       'XSMTVDotII' (SpacemiT Vector Extension for Matrix 2.0)
```

源码侧：

- `grep -rl XSMTVDotII /mnt/k3work/llvm-src/llvm` 命中 7 个文件，包括 `RISCVFeatures.td`、`RISCVInstrInfoXSpacemiT.td`、`RISCVProcessors.td`、`llvm/test/MC/RISCV/xsmtvdotii-valid.s`。
- `RISCVProcessors.td:821` 的 `SPACEMIT_A100` 明确带 `FeatureVendorXSMTVDotII`。
- `llvm/test/MC/RISCV/xsmtvdotii-valid.s` 的 RUN 行就是 `llvm-mc -triple=riscv64 -mcpu=spacemit-a100`，覆盖 `smt.vmadot`、`smt.vmadot1`、`smt.vmadot.sp` 等；`RISCVInstrInfoXSpacemiT.td` 里有 `smt.vfwmadot`/`vfwmadot1/2/3`。
- 这说明 **IME2 不是“clang 接受一个字符串”**，而是有完整 MC/CodeGen/CPU model 支持；可以用 `llvm-mc` + `llvm-objdump` 做确定性验收。

**必须注意：本地 `firefox-k3/toolchain/bin` 是手工 shim，不是完整 clang-24 工具链：**

```text
$ cat /mnt/k3work/firefox-k3/toolchain/bin/ld.lld-24
#!/bin/sh
exec /usr/bin/ld.lld-22 "$@"
$ cat /mnt/k3work/firefox-k3/toolchain/bin/llvm-config-24
#!/bin/sh
exec /usr/bin/llvm-config-22 "$@"
```

也就是说：本地 `clang-24` 是真的（提交 f59949b），但 **lld-24 与 llvm-config-24 是 lld-22/llvm-config-22 的转发**。用于本地“编译+链接”通常能工作（链接器不需要认识 IME2 指令），但它不能作为打包产物，也不能让 `llvm-config-24` 返回正确的 LLVM 24 头文件/库路径。要做 PPA 包，必须自己构建真正的 `lld-24`、`llvm-config-24`。

### 1.2 Ubuntu 26.04 档案现状

| 包 | 版本 | 结论 |
|---|---|---|
| `clang-22` | `1:22.1.2-1ubuntu1`（resolute/universe） | 已安装；档案最高 22 |
| `clang-23`、`clang-24` | 无候选 | 档案没有 |
| `lld-22` | `1:22.1.2-1ubuntu1` | 有 |
| `llvm-22-dev` | `1:22.1.2-1ubuntu1` | 有 |
| `libclang-22-dev` | `1:22.1.2-1ubuntu1` | 有 |
| `rustc-1.97` | `1.97.1+dfsg~26.04-0ubuntu1~26.04.1` | 有；`ldd` 显示 `libLLVM.so.22.1 => /usr/lib/riscv64-linux-gnu/libLLVM.so.22.1` |

`clang-22` 对 IME2 的态度（实测）：

```text
$ clang-22 --print-supported-extensions | grep -i smtvdot
    xsmtvdot             1.0       'XSMTVDot' (SpacemiT Vector Dot Product Extension)
# 没有 xsmtvdotii
$ clang-22 --print-supported-cpus | grep -i spacemit
    spacemit-x60
# 没有 spacemit-a100
```

所以：**档案 clang-22 只能做 IME1（xsmtvdot），不能做 IME2（xsmtvdotii）**；而且它的 CPU model 只有 `spacemit-x60`，没有 `spacemit-a100`。这直接决定 (d) 方案的能力边界。

### 1.3 本机 GCC 17（SpacemiT 定制）

| 项 | 值 |
|---|---|
| 路径 | `/opt/riscv-spacemit/bin/riscv64-linux-gnu-g++` |
| 版本 | `riscv64-linux-gnu-g++ (GCC) 17.0.0 20260928 (experimental)` |
| configure | `--prefix=/opt/riscv-spacemit --target=riscv64-linux-gnu --enable-languages=c,c++ --with-arch=rv64gc --with-abi=lp64d --disable-multilib --with-newlib --disable-nls --disable-werror` |
| IME2 证据 | `cc1plus` 字符串含 `xsmtvdotii`；`-march=rv64gcv_zba_zfh_zvfh_zicbop_xsmtvdot_xsmtvdotii` 预处理通过（`-E -x c /dev/null`，exit 0）；`-mtune=spacemit-a100` 同样通过 |
| 源码 | **本机没有 GCC 17 源码/补丁树**，只有安装好的二进制 |

注意两点：

1. 它是 `--with-newlib` 的定制交叉工具链，不等于可直接打进 Ubuntu PPA 的 Linux GCC 17。
2. 上游 GCC 17 是否自带 `xsmtvdotii`，本机没有源码可证；本机这个 GCC 17 更像 SpacemiT 的 vendor 构建。**打包 GCC 17 的前提是先拿到这份 vendor 源码/补丁**，否则不可落地。

---

## 2. Debian/Ubuntu 的 llvm-toolchain 源码包结构

### 2.1 档案里 `llvm-toolchain-22` 是怎么打的

Debian packaging（Salsa 分支 `22`，Ubuntu 22.1.2 同源）关键点：

| 项 | 内容 | 证据 |
|---|---|---|
| 源码包名 | `llvm-toolchain-22` | `debian/control` 首行 |
| Build-Depends | `debhelper-compat (= 11), cmake, ninja-build, chrpath, texinfo, sharutils, libelf-dev, libffi-dev, libedit-dev, libncurses-dev, swig, python3-dev, libxml2-dev, zlib1g-dev, libzstd-dev, lld | hello, ...` 以及 `libc++1/libomp5/libllvm23` 等 | Debian `debian/control` |
| 构建项目 | `PROJECTS = clang;clang-tools-extra;lld;cross-project-tests;mlir` | `debian/rules:13` |
| Runtimes | `RUNTIMES = compiler-rt;libcxx;libcxxabi` | `debian/rules:68` |
| 阶段 1 目标 | `-DLLVM_TARGETS_TO_BUILD=Native`（在 riscv64 上即 RISCV） | `debian/rules:1215` |
| 阶段 2 | `-DCLANG_ENABLE_BOOTSTRAP=ON`，用 stage1 clang 再编一遍（stage2） | `debian/rules:1259+` |
| 安装前缀 | `-DCMAKE_INSTALL_PREFIX=/usr/lib/llvm-22` | `debian/rules:1208`；`LLVM_DIR=usr/lib/llvm-22`（rules:48） |
| 链接并行 | `-DLLVM_PARALLEL_LINK_JOBS=4` | `debian/rules:371,519` |
| 二进制包数 | 40+（clang、clang-tools、libclang、libllvm、lld、lldb、mlir、flang、libc++、openmp…） | `debian/control` |

Debian 的 `clang-X.Y.install.in` 结构（可直接借鉴）：

```text
@LLVM_DIR@/bin/clang
@LLVM_DIR@/bin/clang++
@LLVM_DIR@/bin/clang-cpp
@LLVM_DIR@/bin/clang-scan-deps
@LLVM_DIR@/bin/clang-cl
@LLVM_LIBDIR@/cmake/clang/*.cmake
@LLVM_DIR@/share/clang/bash-autocomplete.sh

usr/bin/clang-@LLVM_VERSION@
usr/bin/clang++-@LLVM_VERSION@
usr/bin/clang-cpp-@LLVM_VERSION@
usr/bin/clang-scan-deps-@LLVM_VERSION@
usr/bin/clang-cl-@LLVM_VERSION@
```

`lld-X.Y.install.in`：

```text
@LLVM_DIR@/bin/ld.lld*
@LLVM_DIR@/bin/ld64.lld*
@LLVM_DIR@/bin/lld-*
@LLVM_DIR@/bin/lld
@LLVM_DIR@/bin/wasm-ld

usr/bin/lld-link-@LLVM_VERSION@
usr/bin/ld.lld-@LLVM_VERSION@
usr/bin/ld64.lld*-@LLVM_VERSION@
usr/bin/lld-@LLVM_VERSION@*
usr/bin/wasm-ld-@LLVM_VERSION@
```

Ubuntu 22.1.2 的包布局（`dpkg -L`，可作为最小包的镜像）：

```text
/usr/bin/clang-22 -> ../lib/llvm-22/bin/clang
/usr/bin/clang++-22 -> ../lib/llvm-22/bin/clang++
/usr/bin/llvm-config-22 -> ../lib/llvm-22/bin/llvm-config
/usr/bin/lld-22 -> ../lib/llvm-22/bin/lld
/usr/bin/ld.lld-22 -> ../lib/llvm-22/bin/ld.lld
/usr/lib/llvm-22/include/clang-c/*.h
/usr/lib/llvm-22/lib/libclang-22.so.1
/usr/lib/llvm-22/lib/libclang-22.so.22
/usr/lib/riscv64-linux-gnu/libclang-22.so.1
```

### 2.2 LLVM 24 的 Debian packaging 现状

Debian 还没有 `llvm-toolchain-24` release 分支；24 在 Debian 里叫 **`llvm-toolchain-snapshot`**：

| 项 | 值 |
|---|---|
| 源码包 | `llvm-toolchain-snapshot` |
| 版本 | `1:24~++20261025103442+7e3c57157096-1~exp1` |
| 发行版 | experimental |
| 二进制 | `llvm-24`、`clang-24`、`libclang-24-dev` 等 |
| riscv64 | **没有**（`packages.debian.org/experimental/riscv64/llvm-24/download` → “No such package”；buildd 也没有 riscv64 条目） |
| amd64/arm64 | 有 |

这意味着：

- 可以拿 Debian `snapshot` 分支的 `debian/` 作为参考，但它为“全量 LLVM”设计，直接上传 PPA 会复现 8–11 天的构建。
- 不能把 Debian experimental 的二进制直接塞进 PPA（PPA 只收源码包；见 §4.5）。

### 2.3 最小方案：`llvm-toolchain-24`（推荐实现）

目标：只提供 Firefox/Thunderbird 构建真正需要的 5 类东西：`clang-24`、`lld-24`、`libclang-24-dev`（含 `libclang.so`）、`llvm-24-dev`（含 `llvm-config-24` 与头文件）、`llvm-24` 工具。其余全部砍掉。

#### 2.3.1 二进制包拆分

| 二进制包 | 关键文件 | 依赖 |
|---|---|---|
| `clang-24` | `/usr/lib/llvm-24/bin/{clang,clang++,clang-cpp,clang-cl}`；`/usr/bin/clang-24` 等符号链接 | `libclang-common-24-dev`, `libc6-dev`, `binutils` |
| `libclang-common-24-dev` | `/usr/lib/llvm-24/lib/clang/24/include/*`（clang 内建头，`stddef.h`/`stdarg.h` 等） | `${misc:Depends}` |
| `libclang1-24` | `/usr/lib/llvm-24/lib/libclang-24.so.24*`；`/usr/lib/riscv64-linux-gnu/libclang-24.so.24` | `${shlibs:Depends}`, `${misc:Depends}` |
| `libclang-24-dev` | `/usr/lib/llvm-24/include/clang-c/*.h`；`/usr/lib/llvm-24/lib/libclang.so`（→ `libclang-24.so.24`） | `libclang1-24`, `libclang-common-24-dev` |
| `llvm-24` | `/usr/lib/llvm-24/bin/*`（`llvm-config`、`llvm-ar`、`llvm-nm`、`llvm-objcopy`、`llvm-objdump`、`llvm-readelf`、`llvm-strip`、`llvm-ranlib`、`llvm-mc`、`llvm-as`、`llvm-dis`、`llc`、`opt`、`llvm-link`、`llvm-symbolizer` 等）；`/usr/bin/*-24` 符号链接 | `${shlibs:Depends}`, `${misc:Depends}` |
| `llvm-24-dev` | `/usr/lib/llvm-24/include/llvm*`；`/usr/lib/llvm-24/lib/*.a`；`/usr/lib/llvm-24/lib/cmake/llvm` | `llvm-24`, `zlib1g-dev` |
| `lld-24` | `/usr/lib/llvm-24/bin/{lld,ld.lld,lld-link,wasm-ld}`；`/usr/bin/lld-24`、`/usr/bin/ld.lld-24` | `${shlibs:Depends}`, `${misc:Depends}` |

说明：`libclang` 必须构建为 **shared**。LLVM 的 `clang/tools/libclang/CMakeLists.txt` 在 `LLVM_ENABLE_PIC` 为 ON 时会 `set(ENABLE_SHARED SHARED)`；Linux 默认 `LLVM_ENABLE_PIC=ON`，所以默认会产出 `libclang.so`。Rust bindgen 需要的是 `libclang.so`，不是 `.a`。

#### 2.3.2 `debian/control` 草案

```text
Source: llvm-toolchain-24
Section: devel
Priority: optional
Maintainer: K3 Build <build@example.invalid>
Build-Depends: debhelper-compat (= 13),
               cmake (>= 3.31),
               ninja-build,
               g++,
               python3,
               libelf-dev,
               zlib1g-dev
Standards-Version: 4.7.0
Rules-Requires-Root: no
Homepage: https://llvm.org/

Package: clang-24
Architecture: any
Depends: ${shlibs:Depends}, ${misc:Depends},
         libclang-common-24-dev (= ${binary:Version}),
         libc6-dev, binutils
Description: C, C++ and Objective-C compiler (LLVM 24, RISC-V only)

Package: libclang-common-24-dev
Architecture: any
Depends: ${misc:Depends}
Description: Clang builtin headers (LLVM 24)

Package: libclang1-24
Section: libs
Architecture: any
Depends: ${shlibs:Depends}, ${misc:Depends}
Description: C interface to the Clang library (LLVM 24)

Package: libclang-24-dev
Section: libdevel
Architecture: any
Depends: ${misc:Depends},
         libclang1-24 (= ${binary:Version}),
         libclang-common-24-dev (= ${binary:Version})
Description: Clang library development files (LLVM 24)

Package: llvm-24
Architecture: any
Depends: ${shlibs:Depends}, ${misc:Depends}
Description: Modular compiler and toolchain technologies (LLVM 24)

Package: llvm-24-dev
Section: libdevel
Architecture: any
Depends: ${misc:Depends}, llvm-24 (= ${binary:Version}), zlib1g-dev
Description: LLVM 24 libraries, headers and llvm-config

Package: lld-24
Architecture: any
Depends: ${shlibs:Depends}, ${misc:Depends}
Description: LLVM-based linker (LLVM 24)
```

`cmake (>= 3.31)` 的依据：LLVM 24 的 `llvm/CMakeLists.txt` 开头警告 “Starting with LLVM 24, the minimum version of CMake required to build LLVM will become 3.31.0”；Ubuntu 26.04 档案是 cmake 4.2.3，满足。

#### 2.3.3 `debian/rules` 草案（关键 CMake 选项）

```make
#!/usr/bin/make -f
%:
	dh $@

override_dh_auto_configure:
	cmake -S llvm -B build -G Ninja \
	  -DCMAKE_BUILD_TYPE=Release \
	  -DCMAKE_INSTALL_PREFIX=/usr/lib/llvm-24 \
	  -DLLVM_VERSION_SUFFIX= \
	  -DLLVM_TARGETS_TO_BUILD=RISCV \
	  -DLLVM_ENABLE_PROJECTS="clang;lld" \
	  -DLLVM_ENABLE_RUNTIMES="" \
	  -DLLVM_INCLUDE_TESTS=OFF \
	  -DLLVM_INCLUDE_EXAMPLES=OFF \
	  -DLLVM_INCLUDE_BENCHMARKS=OFF \
	  -DLLVM_INCLUDE_DOCS=OFF \
	  -DLLVM_BUILD_DOCS=OFF \
	  -DLLVM_ENABLE_ASSERTIONS=OFF \
	  -DLLVM_ENABLE_ZSTD=OFF \
	  -DLLVM_ENABLE_LIBXML2=OFF \
	  -DLLVM_ENABLE_FFI=OFF \
	  -DLLVM_ENABLE_TERMINFO=OFF \
	  -DLLVM_ENABLE_LIBEDIT=OFF \
	  -DLLVM_ENABLE_BINDINGS=OFF \
	  -DLLVM_ENABLE_PLUGINS=OFF \
	  -DLLVM_ENABLE_ZLIB=ON \
	  -DLLVM_ENABLE_PIC=ON \
	  -DLLVM_ENABLE_RTTI=ON \
	  -DCLANG_DEFAULT_RTLIB=libgcc \
	  -DCLANG_DEFAULT_LINKER=ld \
	  -DCLANG_DEFAULT_CXX_STDLIB=libstdc++ \
	  -DCLANG_FORCE_MATCHING_LIBCLANG_SOVERSION=ON \
	  -DLLVM_BUILD_LLVM_DYLIB=OFF \
	  -DLLVM_LINK_LLVM_DYLIB=OFF \
	  -DCLANG_LINK_CLANG_DYLIB=OFF \
	  -DLLVM_PARALLEL_LINK_JOBS=2 \
	  -DCMAKE_C_FLAGS_RELEASE="-O2 -DNDEBUG" \
	  -DCMAKE_CXX_FLAGS_RELEASE="-O2 -DNDEBUG"

override_dh_auto_build:
	ninja -C build

override_dh_auto_test:
	# 确定性 IME2 验收，不跑 LLVM 单测
	build/bin/llvm-mc -triple=riscv64 -mcpu=spacemit-a100 -show-encoding \
	  <<< 'smt.vmadot v0, v31, v2, i4' | grep -q 'smt.vmadot'
	build/bin/clang --print-supported-extensions | grep -q xsmtvdotii
	echo 'int main(void){return 0;}' > /tmp/ime2.c
	build/bin/clang -march=rv64gcv_zba_zfh_zvfh_zicbop_xsmtvdot_xsmtvdotii \
	  -c /tmp/ime2.c -o /tmp/ime2.o

override_dh_auto_install:
	DESTDIR=$(CURDIR)/debian/tmp cmake --install build
```

**CMake 选项为什么这样砍：**

| 砍掉的东西 | 选项 | 理由 |
|---|---|---|
| 其他后端 | `LLVM_TARGETS_TO_BUILD=RISCV` | PPA 只在 riscv64 构建；Firefox 不做跨架构编译 |
| lldb/mlir/flang/polly/clang-tools-extra/cross-project-tests | `LLVM_ENABLE_PROJECTS="clang;lld"` | 只保留 Firefox 需要的编译器与链接器 |
| compiler-rt/libcxx/libcxxabi/openmp | `LLVM_ENABLE_RUNTIMES=""` | 用 `CLANG_DEFAULT_RTLIB=libgcc`；Firefox 不链接 libc++ |
| 测试/示例/文档/benchmark | `LLVM_INCLUDE_TESTS=OFF` 等 | 构建时间大头之一 |
| assert 版 | `LLVM_ENABLE_ASSERTIONS=OFF` | Release 包不需要断言 |
| zstd/libxml2/ffi/terminfo/libedit/bindings/plugins | 对应 `OFF` | 减少 Build-Depends 与编译量 |
| 动态 libLLVM/libclang-cpp | `LLVM_BUILD_LLVM_DYLIB=OFF`、`LLVM_LINK_LLVM_DYLIB=OFF`、`CLANG_LINK_CLANG_DYLIB=OFF` | 静态链接，少 2–3 个 runtime 包；`libclang.so` 仍然会按 `LLVM_ENABLE_PIC=ON` 生成 |
| 并行链接内存峰值 | `LLVM_PARALLEL_LINK_JOBS=2` | Launchpad builder 约 24 GB 空闲内存，clang 静态链接峰值高；Debian 自己也用 4 |

**一个关键坑：不要随手设 `CLANG_BUILD_TOOLS=OFF`。** `clang/cmake/modules/AddClang.cmake:167` 在 `CLANG_BUILD_TOOLS=OFF` 时给所有 `add_clang_tool` 加 `EXCLUDE_FROM_ALL`，并在 182 行跳过 install 规则——**clang driver 本身也会被跳过安装**。若确实要省时间，做法是保留 `CLANG_BUILD_TOOLS=ON`（默认），或者 `OFF` 后显式 `ninja clang` 并手工安装 `build/bin/clang`，不要指望 `cmake --install` 帮你装 clang。

#### 2.3.4 install / links 要点

- `clang-24.install`：`usr/lib/llvm-24/bin/clang*`、`usr/lib/llvm-24/lib/clang/24/include/*`。
- `libclang1-24.install`：`usr/lib/llvm-24/lib/libclang-24.so.*`；`libclang1-24.links`：`/usr/lib/llvm-24/lib/libclang-24.so.24 /usr/lib/riscv64-linux-gnu/libclang-24.so.24`（然后 `ldconfig`）。
- `libclang-24-dev.install`：`usr/lib/llvm-24/include/clang-c`；`libclang-24-dev.links`：`/usr/lib/llvm-24/lib/libclang.so /usr/lib/llvm-24/lib/libclang-24.so.24`。
- `llvm-24.install`：`usr/lib/llvm-24/bin/*`（或按白名单挑选）；`llvm-24.links`：`/usr/lib/llvm-24/bin/llvm-config /usr/bin/llvm-config-24` 等。
- `lld-24.install`：`usr/lib/llvm-24/bin/{lld,ld.lld,lld-link,wasm-ld}`；`lld-24.links`：`.../lld /usr/bin/lld-24`、`.../ld.lld /usr/bin/ld.lld-24`。
- `llvm-24-dev.install`：`usr/lib/llvm-24/include`、`usr/lib/llvm-24/lib/*.a`、`usr/lib/llvm-24/lib/cmake`。

安装前缀必须是 `/usr/lib/llvm-24`，因为 clang 通过自身路径找 `../lib/clang/24/include`；`/usr/bin/clang-24` 只是符号链接。

#### 2.3.5 源包版本与 tar

建议：

```text
Source: llvm-toolchain-24
Version: 1:24.0.0~git20261005+f59949b-0ubuntu1~ppa1
Distribution: resolute
orig tar: llvm-toolchain-24_24.0.0~git20261005+f59949b.orig.tar.xz
```

- 用本机 `/mnt/k3work/llvm-src` 的 commit `f59949b`（已验证含 IME2），不要用未验证的更新快照。
- tar 顶层目录必须是 `llvm-toolchain-24-24.0.0~git20261005+f59949b/`；只打包 `llvm/`、`clang/`、`lld/`、`cmake/`、`third-party/`、`LICENSE.TXT`、`README.md`，排除 `.git`（359 MB）和不需要的子项目。压缩前约 2.1 GB，压缩后预计 200–300 MB（本机 `llvm-src` 全树 3.1 GB 含 `.git`；Debian 的 LLVM 22 orig tar 量级也在此范围）。
- `debian/source/format`：`3.0 (quilt)`；`debian/patches/series` 可空。

---

## 3. 构建成本：时间、内存、磁盘

### 3.1 本机实测（最小 clang-only，下界）

- **2h00m53s**：`clang` + `llvm-mc`，RISCV-only，Release，`-j14`（8 核机器），无 lld、无 libclang 共享库、无 install。
- 构建目录 **1.7 GB**，源码 **3.1 GB**。
- 这不是完整最小包（缺 lld、libclang.so、llvm-config、install），所以 **最小包实际会更久**；按增加 lld+libclang+install 估 **3–5 小时**（本机同配置）。
- 峰值内存本机没有精确记录，但 31 GB 内存完成；Launchpad builder 日志显示 **8 核、24 GB 空闲内存、8 GB swap**，静态链接 clang 时需要限制 link 并行（`LLVM_PARALLEL_LINK_JOBS=2`）。

### 3.2 Launchpad 公开构建日志（最重要的成本证据）

**（1）Ubuntu 档案 `llvm-toolchain-22` riscv64（全量 Debian 包）：**

```text
Build Architecture: riscv64
Build-Space: 33146320          # KB ≈ 31.6 GiB
Build-Time: 711154             # 秒 ≈ 197.5 小时 ≈ 8.2 天
Build needed 198:20:14, 33146320k disk space
```

构建页面：`https://launchpad.net/ubuntu/+source/llvm-toolchain-22/1:22.1.2-1ubuntu1/+build/32732755`
日志显示 builder `bos03-riscv64-006`，`Initiating build ... with 8 jobs across 8 processor cores`，`MemFree: 24479436 kB`，`SwapFree: 8388604 kB`。
页面耗时：**Started 2026-04-08，Finished 2026-04-16，took 8 days, 7 hours, 4 minutes, 25.2 seconds**。

**（2）PPA `~karljs/+archive/ubuntu/llvm-22-symbols` 的 riscv64 全量构建：**

```text
Build-Space: 33122796          # ≈ 31.6 GiB
Build-Time: 927518             # 秒 ≈ 257.6 小时 ≈ 10.7 天
Build needed 258:23:44, 33122796k disk space
```

构建页面：`https://launchpad.net/~karljs/+archive/ubuntu/llvm-22-symbols/+build/33601576`
耗时：**Started 2026-09-16，Finished 2026-09-27，took 10 days, 19 hours, 16 minutes**。
发布产物：`.changes` 里 70 个文件，总计 **445,383,065 字节 ≈ 425 MiB**。这说明 **PPA 的 8 GiB 发布配额不是主要瓶颈**（全量 LLVM 才 0.4 GiB），真正的瓶颈是构建墙钟时间与 33 GB 构建空间。

**（3）Debian buildd 对照：**

`https://buildd.debian.org/status/package.php?p=llvm-toolchain-22&suite=sid` 显示：

```text
riscv64  1:22.1.8-4  Building  8h 41m  rv-osuosl-03
amd64    1:22.1.8-4  Installed 8h 32m
arm64    1:22.1.8-4  Installed 9h 33m
ppc64el  1:22.1.8-4  Installed 7h 18m
s390x    1:22.1.8-4  Installed 10h 38m
```

Debian 的 riscv64 机器比 Launchpad 的 bos03-riscv64 快得多（至少对这份包），但仍在 8h41m 时未完成。

**（4）Launchpad 有没有总时长超时？**

- `launchpad-manual` 的 PPA 参考页没有给出“总构建时长上限”。
- 实测 10 天 19 小时的 PPA riscv64 构建成功，说明不存在 12/24 小时的硬超时。
- 但构建机有“长时间无输出”看门狗：Firefox 的 `debian/build/rules.mk:59` 明确写着 `# Stop the buildd from timing out during long links`，并用 `keepalive-wrapper.py 1440` 每 1440 秒输出一次。LLVM 构建输出持续，问题不大；但不要把“没有总超时”理解成“可以随便慢”。

**结论：** 最小包在 Launchpad riscv64 上“能完成”是大概率事件（全量包都能完成），但**墙钟时间不可控**：本机 3–5 小时的活，Launchpad 可能是 1–3 天，甚至更久。必须按“一次性构建、按 commit 钉死、不频繁重编”来设计流程。

---

## 4. 现成的 riscv64 clang-24 有没有？

### 4.1 apt.llvm.org

官方页面（`https://apt.llvm.org/`）明确：

> Packages are available for amd64, i386 (Debian only), s390x and arm64 (aka aarch64).

实测 resolute 的 InRelease：

```text
$ curl -s https://apt.llvm.org/resolute/dists/llvm-toolchain-resolute/InRelease | grep Architectures
Architectures: amd64 s390x arm64
$ curl -s -o /dev/null -w '%{http_code}\n' \
  https://apt.llvm.org/resolute/dists/llvm-toolchain-resolute/main/binary-riscv64/Packages.gz
404
```

**没有 riscv64。** 即使有，apt.llvm.org 也不是 Ubuntu 档案，不能直接当作 PPA 的默认 Build-Depends 源；只能通过“加 PPA/档案依赖”的方式引入（见 §4.5），且属于外部供应链。

### 4.2 Ubuntu 26.04 档案

- `clang-22` = 1:22.1.2-1ubuntu1；`clang-23`/`clang-24` 无候选。
- `lld-22`、`llvm-22-dev`、`libclang-22-dev` 有；24 没有。
- 结论：**档案里没有可用的 clang-24**。

### 4.3 Debian experimental

- 源包 `llvm-toolchain-snapshot`，版本 `1:24~++20261025103442+7e3c57157096-1~exp1`。
- `packages.debian.org/experimental/llvm-24` 只列出 **amd64、arm64**。
- `packages.debian.org/experimental/riscv64/llvm-24/download` 返回 “No such package”。
- `buildd.debian.org` 的 `llvm-toolchain-24` 页面：riscv64 数据库无条目。

**没有 riscv64 二进制。** 而且就算有，PPA 也不能上传预编译二进制（见 §4.5）。

### 4.4 Launchpad PPA

- `https://launchpad.net/ubuntu/+ppas?name_filter=clang-24` → “No matching Personal Package Archive”。
- `...?name_filter=llvm-24` → 同样没有。
- 没有发现可用的 riscv64 clang-24 PPA。

### 4.5 PPA 规则核实（这里纠正任务里的一个前提）

Launchpad 官方手册（`launchpad-manual`，`docs/user/reference/packaging/ppas/ppa.rst`）：

| 规则 | 原文/结论 |
|---|---|
| 只收源码 | “Uploadable artefacts: Source packages only; pre-built binary uploads are rejected” |
| 发布配额 | “Disk space: 8 GiB; larger quotas considered on request” |
| riscv64 | 架构表 “riscv64 — Built by default: no”；需要 PPA 的 **Processors** 设置启用（部分架构只有管理员能开） |
| 跨 PPA 依赖 | **允许**：`create-ppa.rst`：“A PPA can depend on other archives, so that packages published in those archives are available when building packages in your PPA.” 可在 “Edit PPA dependencies” 里添加其他 PPA，默认 pin 500 |
| 默认构建源 | 默认 = 当前 PPA + Ubuntu 档案；其他 PPA 需要显式添加 |

所以：

- “PPA 构建环境只加 Ubuntu 档案 + 本 PPA”**默认成立**，但不是硬限制；可以加外部 PPA。
- “PPA 不能依赖其他 PPA”**不成立**。不过，依赖外部 PPA 会引入可用性/供应链风险；目前也没有现成的 riscv64 clang-24 PPA 可依赖。
- riscv64 构建可行：`karljs` 的 PPA 已经成功构建 riscv64 的 llvm-toolchain-22（见 §3.2），但需要在 PPA 设置里启用 riscv64 并手动 Request builds。

---

## 5. 替代方案对比

| 方案 | 做法 | 风险 | 工作量 | Launchpad 可行性 | 评价 |
|---|---|---|---|---|---|
| **(a) 打包 clang-24** | 自带最小 `llvm-toolchain-24` 源包（RISCV-only、clang+lld、单阶段） | LLVM 24 是 snapshot，ABI/行为可能变；构建 1–3 天；需维护 debian/；PPA 架构需手动开 | 中高（1–2 周工程） | **可行**，但必须最小化；全量 Debian 包 8–11 天不可接受 | **IME2 进 PPA 的唯一干净路线** |
| **(b) 打包 GCC 17** | 把 `/opt/riscv-spacemit` 的 GCC 17 打成 PPA 源包 | 本机只有二进制、没有源码/补丁；`--with-newlib` 不是 Ubuntu Linux 工具链；Firefox Debian 构建是 clang/lld 中心，换 GCC 要改 mozconfig；GCC bootstrap 构建更慢 | 高 | 理论可行，实际缺源码，**不可落地** | 不推荐 |
| **(c) 预编译 clang 塞进 Firefox 源 tar** | 把本地 clang-24 二进制放进 `firefox.orig.tar.xz`，构建时直接用 | 违反 PPA“源码交付”精神；源码包含二进制、不可复现/审计；tar 体积大（clang 141 MB + libs + lld）；upload/构建风险；许可证/源码义务 | 低–中 | 技术上可能，**政策/维护风险高** | 不推荐 |
| **(d) PPA 只做 IME1/RVV，IME2 仅本地** | 用档案 clang-22 + `-march=...+xsmtvdot`；本地用 clang-24 做 IME2 | PPA 用户没有 IME2；两套产物口径 | 低（1–2 天） | **马上可行** | **推荐的 Phase 1** |

补充：

- (b) 的 GCC 17 虽然本机 `cc1plus` 含 `xsmtvdotii`、能接受 `-march`/`-mtune`，但这是 SpacemiT vendor 构建；没有源码就无法在 PPA 里重建，也无法证明上游 GCC 17 自带 IME2。
- (c) 的“塞二进制”即便绕过 Launchpad 检查，也会让 Firefox 源包失去可复现性；后续安全更新/审计无法解释“这个 clang 从哪来”。
- (d) 的能力边界要写清楚：clang-22 只有 `xsmtvdot`（IME1），CPU model 只有 `spacemit-x60`，没有 `spacemit-a100`；所以 PPA 产物是 **IME1/RVV**，不是 IME2。

---

## 6. 选 (a) 的落地细节

### 6.1 源包版本与 PPA 操作顺序

1. 在 Launchpad 建 PPA，进入 PPA 设置 → **Processors**，勾选 `riscv64`（若不可选，按文档找管理员；`karljs` 的 PPA 证明可开）。
2. 上传 `llvm-toolchain-24` 源包（`dput`），在源码包页面 **Request builds** 选 riscv64。等 `clang-24`/`lld-24`/`libclang-24-dev`/`llvm-24-dev` 发布。
3. 上传 Firefox/Thunderbird 源包。其 Build-Depends 里的 `clang-24` 等会从 **同一个 PPA + Ubuntu 档案** 解析（默认行为，不需要额外加依赖）。
4. 如果非要依赖外部工具链 PPA：PPA 设置 → “Edit PPA dependencies” → 添加 `owner/ppa`，pin 500；但本报告不建议把它作为主路径。
5. 关闭/谨慎开启 PPA 的 “Build debug symbols”：全量 LLVM 发布物才 425 MiB，但 ddeb 会显著放大；8 GiB 配额要留余量。

### 6.2 Firefox 侧要改什么

当前 `sources/ff-debian/debian/control`：

```text
clang-22 | clang-21 | clang-20 | clang-19,
libclang-22-dev | libclang-21-dev | libclang-20-dev | libclang-19-dev,
llvm-22-dev | llvm-21-dev | llvm-20-dev | llvm-19-dev,
lld-22 | lld-21 | lld-20 | lld-19,
cargo-1.97 | cargo-1.94 | cargo-1.93 | cargo-1.90,
rustc-1.97 | rustc-1.94 | rustc-1.93 | rustc-1.90,
```

改为（24 放最前，保证命中）：

```text
clang-24 | clang-22 | clang-21 | clang-20 | clang-19,
libclang-24-dev | libclang-22-dev | libclang-21-dev | libclang-20-dev | libclang-19-dev,
llvm-24-dev | llvm-22-dev | llvm-21-dev | llvm-20-dev | llvm-19-dev,
lld-24 | lld-22 | lld-21 | lld-20 | lld-19,
cargo-1.97 | cargo-1.94 | cargo-1.93 | cargo-1.90,
rustc-1.97 | rustc-1.94 | rustc-1.93 | rustc-1.90,
```

`debian/build/rules.mk`：

```text
LLVM_VERSIONS = 24 22 21 20 19
```

该文件的 `DEB_LLVM_VERSION` 用 `which clang-$(version)` 选第一个；`CC=clang-$(DEB_LLVM_VERSION)`、`CXX=clang++-...`。`debian/config/mozconfig.in` 已经是 `ac_add_options CC=clang-@DEB_LLVM_VERSION@`、`--enable-linker=lld-@DEB_LLVM_VERSION@`，不需要改模板。

IME2 编译 flags（只给 C/C++，不要给 rustc）：

```text
-march=rv64gcv_zba_zfh_zvfh_zicbop_xsmtvdot_xsmtvdotii -mtune=spacemit-a100
```

建议加在 `debian/build/rules.mk` 的 `CFLAGS`/`CXXFLAGS`（在 `export CFLAGS := $(strip ...)` 之前），或用 `debian/rules` 的 riscv64 条件追加。注意：

- `-mtune=spacemit-a100` 只有 clang-24 支持；clang-22 只有 `spacemit-x60`。
- **不要**把 `+xsmtvdotii` 写进 `RUSTFLAGS`：rustc-1.97 的 target-feature 列表没有 `xsmtvdotii`，会直接报 unknown feature。
- 如果同时保留 clang-22 回退，必须按编译器版本分开 flags：24 → `xsmtvdotii`；22 → `xsmtvdot`。

Thunderbird 是另一套 packaging：`sources/tb-debian` 是 140.17.0（noble），`debian/control` 还是 `clang-21 | ... | clang-18`、`rustc-1.85 | ...`，`debian/build/rules.mk` 是 `LLVM_VERSIONS = 21 20 19 18`。如果 Thunderbird 也要 IME2，同样要加 24 并改 flags；但它的 series/版本与 Firefox 160 不同，不能假设同一份改动直接复用。

### 6.3 验收清单（不能只看“编过了”）

1. **工具链包：**
   ```bash
   clang-24 --version
   clang-24 --print-supported-extensions | grep xsmtvdotii
   lld-24 --version
   llvm-config-24 --version
   ls /usr/lib/llvm-24/lib/libclang.so
   ```
2. **汇编器级 IME2（确定性）：**
   ```bash
   printf 'smt.vmadot v0, v31, v2, i4\n' | \
     llvm-mc-24 -triple=riscv64 -mcpu=spacemit-a100 -show-encoding
   # 期望 encoding: [0x2b,0xb0,0x2f,0xc2]（见 llvm/test/MC/RISCV/xsmtvdotii-valid.s）
   ```
3. **编译器接受 IME2 flags：**
   ```bash
   echo 'int main(void){return 0;}' > /tmp/t.c
   clang-24 -march=rv64gcv_zba_zfh_zvfh_zicbop_xsmtvdot_xsmtvdotii \
     -mtune=spacemit-a100 -c /tmp/t.c -o /tmp/t.o
   ```
4. **Firefox 构建真正用了 clang-24/lld-24：** 在 build log 里确认 `CC=clang-24`、`CXX=clang++-24`、`--enable-linker=lld-24`；不能只看 Build-Depends。
5. **IME2 指令真的出现了：** 对 Firefox 的关键对象/`libxul.so` 做
   ```bash
   llvm-objdump-24 -d --mcpu=spacemit-a100 -M no-aliases libxul.so | \
     grep -E 'smt\.(vfwmadot|vmadot)'
   ```
   如果为 0，说明 flags 没进编译，或代码路径根本没有 IME2 —— 参考 ncnn 的教训：**“编过了”不等于 IME2 编进去了**。
6. **硬件兼容性：** 带 `xsmtvdotii` 的产物在非 SpacemiT/非 K3 的 RISC-V 机器上可能 SIGILL；PPA 产物要明确标注“K3/IME2 专用”，或另出一个 generic 构建。

---

## 7. rustc 是否必须自建（LLVM 24）

### 7.1 事实

```text
$ rustc-1.97 --version
rustc 1.97.1 (8bab26f4f 2026-07-14) (built from a source tarball)
$ ldd $(which rustc-1.97) | grep -i llvm
    libLLVM.so.22.1 => /usr/lib/riscv64-linux-gnu/libLLVM.so.22.1
$ rustc-1.97 --print target-features --target riscv64gc-unknown-linux-gnu | grep -i smt
    xsmtvdot   - 'XSMTVDot' (SpacemiT Vector Dot Product Extension).
# 没有 xsmtvdotii
```

### 7.2 自建成本（实测参考）

Ubuntu `rustc-1.97` 的 riscv64 PPA 构建日志（`~rust-toolchain/+archive/ubuntu/staging/+build/33564274`）：

```text
Build-Space: 41680652          # KB ≈ 39.8 GiB
Build-Time: 121160             # 秒 ≈ 33.7 小时
Build needed 33:54:12, 41680652k disk space
```

页面耗时：**Started 2026-09-07，Finished 2026-09-08，took 1 day, 10 hours, 9 minutes**；发布物 91.6 MiB。
注意：这还是链 **LLVM 22** 的 rustc；改成 LLVM 24 还要加 LLVM 24 的构建依赖、改 bootstrap 的 `--llvm-root`/submodule、处理 rustc 对 LLVM 版本的检查，时间只会更长。

### 7.3 结论

- **不必要**：Firefox 的 C/C++ 单元用 clang-24 拿 IME2；Rust 单元继续用 rustc-1.97（LLVM 22，IME1 可用）。两者产出的对象可以正常链接（lld-24/ld.lld-24 只做 ELF 链接，不需要理解 IME2）。
- **不划算**：为 Rust 侧 IME2 重建 rustc，至少是 34 小时 CPU + 42 GB 构建空间 + 一套 rustc packaging 维护；而收益只是在 Rust 代码里多一种指令选择。
- **例外**：如果后续确认 Firefox 的 Rust 热路径必须用 IME2 intrinsics，再单独立项；届时优先考虑把热路径下沉到 C++（clang-24 编译），而不是重建 rustc。

---

## 8. 风险清单

| # | 风险 | 影响 | 缓解 |
|---|---|---|---|
| 1 | LLVM 24 是 snapshot，不是 release | API/行为/ABI 变动；未来重建结果不同 | 钉死 commit `f59949b` 与源包版本；保留 orig tar 与 `.dsc` |
| 2 | Launchpad riscv64 构建墙钟不可控 | 1–3 天，阻塞 Firefox 迭代 | 工具链单独 PPA/单独构建；构建一次后固定；Firefox 构建只依赖已发布的二进制 |
| 3 | 全量 Debian packaging 直接复用 | 8–11 天构建、33 GB 空间 | 只用最小 debian/：RISCV-only、clang+lld、单阶段、无 tests/docs/runtimes |
| 4 | PPA riscv64 非默认架构 | 上传后不自动构建 | 在 PPA Processors 启用 riscv64；手动 Request builds；若受限找 Launchpad admin |
| 5 | PPA 8 GiB 配额 | 发布物超限 | 全量 LLVM 才 425 MiB，最小包更小；关闭/谨慎开启 debug symbols |
| 6 | IME2 flags 没进编译 | 产物实际是 IME1，性能结论错误 | 用 `llvm-mc -mcpu=spacemit-a100` + `llvm-objdump` 检查 `smt.*`；检查 Firefox build log 的 CC/CXX/linker |
| 7 | rustc 不认识 `xsmtvdotii` | 构建直接失败 | 只给 C/C++ 加 IME2 flags；RUSTFLAGS 不加 |
| 8 | 本地 `lld-24`/`llvm-config-24` 是 shim | 误以为本地工具链完整；打包时缺件 | 打包必须自建真 lld-24/llvm-config-24；本地链接继续用 lld-22 可以，但别拿 shim 当交付 |
| 9 | 非 K3 硬件兼容性 | 带 IME2 的 Firefox 在普通 RISC-V 上 SIGILL | PPA 明确标注硬件要求；或分 generic / K3 两个构建 |
| 10 | Thunderbird 与 Firefox packaging 分叉 | 只改 Firefox 漏掉 Thunderbird | 分别改 `tb-debian` 的 control/rules；Thunderbird 140 还是 clang-21/rustc-1.85 基线 |
| 11 | 依赖外部 PPA | 供应链/可用性风险；外部 PPA 可能撤包 | 默认只用 Ubuntu 档案 + 本 PPA；必须用时固定 pin 并镜像源包 |
| 12 | 预编译 clang 塞 tar | 政策/可复现性/体积风险 | 不采用；坚持源码包 |

---

## 9. 决策建议

### 9.1 推荐路线（按优先级）

**Phase 1（立即可做，1–2 天）：走 (d)。**

- PPA 用档案 `clang-22` + `lld-22`，Firefox/Thunderbird 只加 IME1/RVV flags：
  `-march=rv64gcv_zba_zfh_zvfh_zicbop_xsmtvdot -mtune=spacemit-x60`
- 交付“PPA 可安装的 IME1/RVV 版本”；IME2 只在本地用 clang-24 构建/对标。
- 这样不引入任何新工具链源包，PPA 构建风险最低。

**Phase 2（IME2 必须进 PPA 时）：走 (a)。**

- 新增最小 `llvm-toolchain-24` 源包（§2.3），只做 RISCV + clang + lld，单阶段 Release。
- PPA 先发工具链，再发 Firefox/Thunderbird；Firefox Build-Depends 加 24；CFLAGS/CXXFLAGS 加 IME2 flags；rustc 保持 1.97。
- 预算：工程 1–2 周；Launchpad 工具链构建 1–3 天；Firefox 构建另算。构建成功后按 commit 钉死，不频繁重编。

### 9.2 不做什么

- **不打包 GCC 17**：本机只有 vendor 二进制，没有源码/补丁；`--with-newlib` 也不是 Ubuntu PPA 的 Linux 工具链形态。
- **不把预编译 clang 塞进 Firefox 源 tar**：政策、可复现性、体积都不划算。
- **不重建 rustc**：除非确认 Rust 热路径必须用 IME2，否则 34 小时/42 GB 的成本没有回报。
- **不要直接复用 Debian 全量 `llvm-toolchain` packaging**：8–11 天的 Launchpad 构建时间会拖垮迭代。

### 9.3 Go / No-Go 判据

- 最小 clang-24 包在 PPA 上 **两次尝试均超过 3 天或失败** → 回退 (d)，IME2 留在本地。
- Firefox 用 clang-24 构建出现 LLVM 24 snapshot 的编译/链接回归 → 回退 (d)，等 LLVM 24 release 或换更稳的 commit。
- 如果 IME2 只是本地性能验证需求 → 直接 (d)，不启动 (a)。

---

## 附录 A：关键证据与 URL

### A.1 本机命令

```bash
# LLVM 版本 / commit
cat /mnt/k3work/llvm-src/cmake/Modules/LLVMVersion.cmake
git -C /mnt/k3work/llvm-src log -1 --format='%H %cd'
/mnt/k3work/llvm-build/bin/clang --version
/mnt/k3work/llvm-build/bin/clang --print-supported-extensions | grep smtvdot

# 本地 shim（重要）
cat /mnt/k3work/firefox-k3/toolchain/bin/ld.lld-24
cat /mnt/k3work/firefox-k3/toolchain/bin/llvm-config-24

# 本地构建耗时/磁盘
stat -c '%y %n' /mnt/k3work/build_llvm.sh /mnt/k3work/llvm_cmake.log \
  /mnt/k3work/llvm_make.log /mnt/k3work/llvm-build/bin/clang-24
du -sh /mnt/k3work/llvm-build /mnt/k3work/llvm-src

# 档案工具链
apt-cache policy clang-22 lld-22 llvm-22-dev libclang-22-dev rustc-1.97
ldd $(which rustc-1.97) | grep -i llvm
rustc-1.97 --print target-features --target riscv64gc-unknown-linux-gnu | grep -i smt

# 包布局
dpkg -L clang-22 | grep -E 'bin/|lib/clang'
dpkg -L libclang-22-dev | grep -E 'clang-c|libclang|\.so'
dpkg -L llvm-22-dev | grep -E 'llvm-config|include/llvm/Config|libLLVM|cmake'
dpkg -L lld-22
```

### A.2 Launchpad / 档案

- PPA 参考（源码 only、8 GiB、riscv64 非默认）：`https://raw.githubusercontent.com/canonical/launchpad-manual/main/docs/user/reference/packaging/ppas/ppa.rst`
- PPA 创建/Processors/依赖：`https://raw.githubusercontent.com/canonical/launchpad-manual/main/docs/user/how-to/packaging/create-ppa.rst`
- Ubuntu llvm-toolchain-22 riscv64 构建（198h）：`https://launchpad.net/ubuntu/+source/llvm-toolchain-22/1:22.1.2-1ubuntu1/+build/32732755`
- PPA llvm-toolchain-22 riscv64 构建（258h）：`https://launchpad.net/~karljs/+archive/ubuntu/llvm-22-symbols/+build/33601576`
- Debian buildd llvm-toolchain-22：`https://buildd.debian.org/status/package.php?p=llvm-toolchain-22&suite=sid`
- Debian experimental llvm-24：`https://packages.debian.org/experimental/llvm-24`
- apt.llvm.org：`https://apt.llvm.org/`（Architectures 行实测 `amd64 s390x arm64`）
- Ubuntu resolute 包：`https://packages.ubuntu.com/resolute/clang-22`（本地 `apt-cache policy` 同）
- rustc-1.97 riscv64 构建（33.9h/41.7GB）：`https://launchpad.net/~rust-toolchain/+archive/ubuntu/staging/+build/33564274`

### A.3 Debian packaging 参考

- `llvm-toolchain` Salsa 分支 `22`：`https://salsa.debian.org/pkg-llvm-team/llvm-toolchain/-/tree/22/debian`
- 分支 `snapshot`（LLVM 24）：`https://salsa.debian.org/pkg-llvm-team/llvm-toolchain/-/tree/snapshot/debian`
- `debian/rules`（PROJECTS/RUNTIMES、Native、parallel link jobs、install prefix）：`https://salsa.debian.org/pkg-llvm-team/llvm-toolchain/-/raw/22/debian/rules`
- `clang-X.Y.install.in` / `lld-X.Y.install.in`：salsa 同目录
- LLVM 24 IME2 测试：`/mnt/k3work/llvm-src/llvm/test/MC/RISCV/xsmtvdotii-valid.s`
- LLVM 24 A100 CPU model：`/mnt/k3work/llvm-src/llvm/lib/Target/RISCV/RISCVProcessors.td:821`

---

## 附录 B：本次调研“未执行”的检查（明确披露）

- 没有实际构建 `llvm-toolchain-24` 源包；3–5 小时本机/1–3 天 Launchpad 是**基于本机 2h clang-only 实测 + 全量包 198h 实测的估算**，不是实测值。
- 没有在 PPA 上传/构建；riscv64 Processors 是否对目标 PPA 可选，取决于 Launchpad 账号/团队权限；文档说部分架构只有管理员能开。
- 没有验证 `-mcpu=spacemit-a100` 在 clang-24 上的完整代码生成路径；只验证了扩展列表、源码 CPU model、MC 测试存在。实际 Firefox 构建仍需按 §6.3 做 `llvm-objdump` 验收。
- 没有验证 Thunderbird 140（noble）在 resolute PPA 的 series 兼容性；它当前是 noble 源包，若 PPA 目标为 resolute，需要先解决 series/依赖差异。
