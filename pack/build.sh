#!/bin/bash
#
# Fetch MAME 0.289, apply the SYS16 patches, and build just the National
# Semiconductor drivers rather than the whole of MAME.
#
#   GENIX_WORK=$HOME/genix pack/build.sh
#
# Everything that separates this from stock MAME is in patch/patches.
#
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
REPO=$(dirname "$HERE")
WORK=${GENIX_WORK:-$HOME/genix}

say() { printf '%s\n' "$*"; }

case "$WORK" in
    *[[:space:]]*) say "GENIX_WORK contains a space: $WORK"; exit 1 ;;
esac

DEPS="git build-essential python3 libsdl2-dev libsdl2-ttf-dev libfontconfig1-dev libpulse-dev qtbase5-dev"
MISSING=""
for p in $DEPS; do
    dpkg -s "$p" >/dev/null 2>&1 || MISSING="$MISSING $p"
done
if [ -n "$MISSING" ]; then
    say "These packages are missing:$MISSING"
    say "    sudo apt-get install -y$MISSING"
    exit 1
fi

mkdir -p "$WORK"
cd "$WORK"

if [ ! -d mame ]; then
    say "Fetching MAME 0.289.  This is about 1.3 GB."
    git clone --depth 1 --branch mame0289 https://github.com/mamedev/mame.git mame
fi

cd mame
if ! git log --oneline -1 2>/dev/null | grep -q "pack header"; then
    say "Applying the SYS16 patches."
    git config user.email genix@localhost
    git config user.name genix
    git am "$REPO"/patch/patches/*.patch
fi

# Memory, not processors, is what limits a MAME build: about 2.5 GB per job.
KB=$(awk '/MemTotal/ {print $2}' /proc/meminfo)
JOBS=$(( KB / 1024 / 2500 ))
[ "$JOBS" -lt 1 ] && JOBS=1
CPUS=$(nproc)
[ "$JOBS" -gt "$CPUS" ] && JOBS=$CPUS
say "Building with $JOBS parallel job(s)."

make SUBTARGET=genix \
     SOURCES=src/mame/natsemi/sys16.cpp,src/mame/natsemi/icm3216.cpp,src/mame/natsemi/ns32kdb.cpp \
     REGENIE=1 NOWERROR=1 -j"$JOBS"

strip genix
say ""
say "Built: $WORK/mame/genix"
say "Put the sys16 romset in $WORK/roms/sys16.zip and see pack/README.txt."
