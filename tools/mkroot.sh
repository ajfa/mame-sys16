#!/bin/bash
#
# Assemble the GENIX root filesystem tree.
#
#   mkroot.sh <opus5-distribution-tree> <output-tree> <kernel-coff>
#
# The kernel is National's, converted to the a.out the SYS16 ROM can boot.
# Everything else comes from the Opus5 distribution floppies, which are the
# same AT&T System V R2 ported to the same ns32k COFF: the GENIX archives
# that survive hold only /usr, with no /bin and no /etc at all, so there is
# no GENIX sh, ls or init anywhere to take.
set -euo pipefail

DIST=${1:?usage: mkroot.sh <dist> <out> <kernel>}
ROOT=${2:?}
KERNEL=${3:?}
TOOLS=$(dirname "$(readlink -f "$0")")

rm -rf "$ROOT"
mkdir -p "$ROOT"

python3 "$TOOLS/coff2genix.py" "$KERNEL" "$ROOT/vmunix"

cp -a "$DIST/bin" "$ROOT/bin"
cp -a "$DIST/etc" "$ROOT/etc"
cp -a "$DIST/lib" "$ROOT/lib"
cp -a "$DIST/usr" "$ROOT/usr"
mkdir -p "$ROOT/tmp" "$ROOT/mnt"

# Opus5's own /etc/init is the one that works with this kernel
: > "$ROOT/etc/mnttab"
rm -rf "$ROOT/opus" "$ROOT/bck"

# The console comes up with the System V defaults, where the erase character
# is # and the interrupt is DEL, so the Backspace key does not erase and the
# Delete key kills the line.  Nothing here is a login shell, so no profile is
# ever read and nothing would fix that by itself: set the line up from
# inittab, before the shell is started.
cat > "$ROOT/etc/inittab" <<'EOF'
is:s:initdefault:
tt::bootwait:/bin/stty erase '^h' kill '^u' intr '^c' echoe </dev/console >/dev/console 2>&1
co:s:respawn:/bin/sh </dev/console >/dev/console 2>&1
EOF

cat > "$ROOT/.profile" <<'EOF'
PATH=/bin:/etc:/usr/bin; export PATH
TZ=PST8PDT; export TZ
EOF

echo "root tree:"
du -sh "$ROOT"
for d in bin etc lib usr; do printf '  %-5s %s\n' "$d" "$(du -sh "$ROOT/$d" | cut -f1)"; done
printf '  %-5s %s\n' files "$(find "$ROOT" -type f | wc -l)"
