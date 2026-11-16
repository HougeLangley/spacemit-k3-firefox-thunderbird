#!/bin/bash
# Count RVV/IME instructions in the built libxul.so (or a given ELF).
set -euo pipefail
root="${1:-/mnt/k3work/firefox-k3/build/firefox-160.0/obj-riscv64-linux-gnu}"
bin="${2:-$(find "$root" -name 'libxul.so' -type f | head -1)}"
if [ -z "${bin:-}" ] || [ ! -f "$bin" ]; then
  echo "libxul.so not found under $root" >&2
  exit 1
fi
echo "ELF: $bin"
ls -lh "$bin"
tmp=$(mktemp /tmp/libxul-disasm.XXXXXX.s)
llvm-objdump-22 -d "$bin" > "$tmp" 2>/dev/null || objdump -d "$bin" > "$tmp"
for pat in vmadot vfwmadot vsetvli 'vle8\.v' 'vse8\.v' vfmacc vwmacc vwadd; do
  printf '%-12s %s\n' "$pat" "$(grep -cE "\b$pat" "$tmp" || true)"
done
echo "disasm: $tmp"
