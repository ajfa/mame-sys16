#!/bin/bash
#
# Run the emulated SYS16.
#
#   pack/run.sh              open the machine in a window and boot GENIX
#   pack/run.sh --terminal   run it inside this terminal instead, no window
#   pack/run.sh --monitor    open the window but stop at the ROM monitor
#   pack/run.sh --check      boot it, prove it reached a shell, and stop
#
# It expects, under GENIX_WORK (default $HOME/genix):
#
#   mame/genix        the emulator, from pack/build.sh
#   roms/sys16.zip    the romset, which you supply
#   disk/dc0.img      a pack for unit 0, from tools/mkdisk.py
#   disk/dc1.img      the system pack for unit 1, from tools/mkdisk.py + mkfs.py
#
set -uo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
WORK=${GENIX_WORK:-$HOME/genix}

say()  { printf '%s\n' "$*"; }
die()  { printf 'error: %s\n' "$*" >&2; exit 1; }

case "$WORK" in
    *[[:space:]]*) die "GENIX_WORK contains a space: $WORK" ;;
esac

MODE=window
for a in "$@"; do
    case "$a" in
        --terminal) MODE=terminal ;;
        --check)    MODE=check ;;
        --monitor)  MODE=monitor ;;
        -h|--help)  sed -n '2,16p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) die "unknown option: $a" ;;
    esac
done

MAME=$WORK/mame/genix
[ -x "$MAME" ] || die "no emulator at $MAME; run pack/build.sh first"
[ -f "$WORK/roms/sys16.zip" ] || die "no romset at $WORK/roms/sys16.zip"
for d in 0 1; do
    [ -f "$WORK/disk/dc$d.img" ] || die "no pack at $WORK/disk/dc$d.img; see tools/mkdisk.py"
done

mkdir -p "$WORK/run"

# Two machines writing the same pack would destroy it, and the damage only
# shows up later as a kernel that loads and then dies.
exec 9> "$WORK/run/disk.lock"
flock -n 9 || die "another session is already using these disks"

if [ "$MODE" = window ] || [ "$MODE" = monitor ]; then
    if [ -z "${DISPLAY:-}" ] && [ -z "${WAYLAND_DISPLAY:-}" ]; then
        say "no desktop here, running inside this terminal instead"
        MODE=terminal
    fi
fi

case "$MODE" in
    check|terminal)
        flock -u 9
        ARGS=(--mame "$MAME" --rompath "$WORK/roms"
              --disk0 "$WORK/disk/dc0.img" --disk1 "$WORK/disk/dc1.img"
              --work "$WORK/run")
        [ "$MODE" = check ] && ARGS+=(--check)
        python3 "$HERE/genixterm.py" "${ARGS[@]}"
        exit $?
        ;;
    window|monitor)
        BOOT=(-autoboot_script "$HERE/bootkey.lua")
        [ "$MODE" = monitor ] && BOOT=()
        say "To shut down: type  /bin/sync  at the GENIX prompt, wait for it to"
        say "come back, then press Esc to close the machine."
        say ""
        "$MAME" sys16 \
            -rompath "$WORK/roms" \
            -conport terminal \
            -hard1 "$WORK/disk/dc0.img" -hard2 "$WORK/disk/dc1.img" \
            -window -nomaximize -nofilter \
            -skip_gameinfo \
            -sound none \
            "${BOOT[@]}" \
            -nvram_directory "$WORK/run/nvram" -cfg_directory "$WORK/run/cfg" \
            -snapshot_directory "$WORK/run/snap" -diff_directory "$WORK/run/diff" \
            -inipath "$WORK/run"
        exit $?
        ;;
esac
