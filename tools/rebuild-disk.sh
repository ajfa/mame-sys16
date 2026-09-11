#!/bin/bash
#
# Rebuild the GENIX disk from the tree in rootfs/.
#
# Put whatever you want on the machine into rootfs/ and run this; it writes a
# fresh disk/dc1.master.img.  Your running disk (disk/dc1.img) is not touched,
# so afterwards run ../run-linux.sh --reset to start from the new one.
#
# Special files cannot be represented in an ordinary directory, so the device
# nodes are listed in genix.spec instead.
#
set -euo pipefail
cd "$(dirname "$0")/.."

command -v python3 >/dev/null || { echo "python3 is not installed" >&2; exit 1; }

BLOCKS=$(python3 -c "import sys; sys.path.insert(0,'tools'); import mkdisk; print(mkdisk.root_blocks())")

python3 tools/mkdisk.py /tmp/genix-disk.$$ >/dev/null
python3 tools/mkfs.py /tmp/genix-fs.$$ "$BLOCKS" rootfs --spec tools/genix.spec --disktab

python3 - "$$" <<'EOF'
import sys
tag = sys.argv[1]
fs = open(f'/tmp/genix-fs.{tag}', 'rb').read()
img = bytearray(open(f'/tmp/genix-disk.{tag}', 'rb').read())
img[0:len(fs)] = fs
open('disk/dc1.master.img', 'wb').write(img)
print('disk/dc1.master.img rebuilt')
EOF

rm -f "/tmp/genix-disk.$$" "/tmp/genix-fs.$$"
echo "run ./run-linux.sh --reset to boot from it"
