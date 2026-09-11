====================================================================
Building and running the SYS16
====================================================================

Ubuntu 22.04. Everything writes under one directory of your choosing:

    export GENIX_WORK=$HOME/genix

Do not use a path with a space in it. MAME's build tooling cannot
cope with one and the scripts refuse rather than fail obscurely.


--------------------------------------------------------------------
1. THE EMULATOR
--------------------------------------------------------------------

    pack/build.sh

Fetches MAME 0.289, applies the patches in patch/patches, and builds
only the National Semiconductor drivers rather than the whole of
MAME. Needs the network, about 1.3 GB of download, and:

    git build-essential python3 libsdl2-dev libsdl2-ttf-dev
    libfontconfig1-dev libpulse-dev qtbase5-dev

It sizes itself by memory rather than by processor count, because
MAME needs roughly 2.5 GB per parallel job. On a 4 GB machine it uses
one job and takes a while.

Leaves the emulator at $GENIX_WORK/mame/genix.


--------------------------------------------------------------------
2. THE ROMS
--------------------------------------------------------------------

    $GENIX_WORK/roms/sys16.zip

The ten EPROMs of the Rev. 3.4 monitor and the two of the disk board
firmware, as dumped in MAME. Not included here.

    $GENIX_WORK/mame/genix -rompath $GENIX_WORK/roms -verifyroms sys16

should say the romset is good before you go on.


--------------------------------------------------------------------
3. THE DISKS
--------------------------------------------------------------------

The machine wants two packs. Unit 1 holds the system; unit 0 can be
empty, but it must have a header, because the disk driver probes
every unit at open time.

    mkdir -p $GENIX_WORK/disk
    tools/mkdisk.py $GENIX_WORK/disk/dc0.img priam70

The drive types are National's own, from the table in the standalone
sources: basf20, 3m20, 3m60, imi20, imi60, priam70. The emulated
controller reads the shape out of the header you just wrote, so any
of them works without rebuilding anything.

For unit 1 you need a root filesystem to put on it. Assemble a tree:

    tools/mkroot.sh <opus5-tree> $GENIX_WORK/root <kernel-coff>

where <opus5-tree> is the Opus5 distribution floppies unpacked (they
are ASCII cpio archives) and <kernel-coff> is unixsys32 from the
System V R2 source release for the Series 32000. mkroot.sh converts
the kernel to the a.out the ROM can boot and writes an inittab that
sets the console line up before the shell starts.

Then build the pack and put the tree on it:

    tools/mkdisk.py $GENIX_WORK/disk/dc1.img priam70
    tools/mkfs.py $GENIX_WORK/root.fs \
        $(python3 -c "import sys; sys.path.insert(0,'tools'); \
                      import mkdisk; print(mkdisk.root_blocks())") \
        $GENIX_WORK/root --spec tools/genix.spec --disktab

and write root.fs over the start of dc1.img. tools/rebuild-disk.sh
does the last two steps for you once the layout is in place.


--------------------------------------------------------------------
4. RUNNING IT
--------------------------------------------------------------------

    pack/run.sh              a window, and it boots GENIX by itself
    pack/run.sh --terminal   inside this terminal, no window
    pack/run.sh --monitor    a window, stopped at the ROM monitor
    pack/run.sh --check      boot it, prove it reached a shell, stop

The machine has no video hardware. Its console is a serial port, so
what the window shows is the terminal on the end of that port. The
window is a window: it is never full screen.

--check never opens anything and never touches the terminal settings,
so it is safe over ssh and in scripts. With no desktop at all, the
window modes fall back to --terminal by themselves and say so.


--------------------------------------------------------------------
5. SHUTTING IT DOWN. READ THIS ONE.
--------------------------------------------------------------------

In a window, at the GENIX prompt:

    /bin/sync

Wait for the prompt to come back, then press Esc.

In --terminal, Ctrl-] then q does both for you: it types the sync,
waits, and then closes the machine. Ctrl-] then x closes it at once
without syncing, and Ctrl-] then ] sends a real Ctrl-] to GENIX.

That order matters. sync writes out what GENIX still had in memory,
and closing the emulator properly flushes and closes the disk image.
There is no shutdown or haltsys in a minimal /bin, so sync is the
whole of a clean shutdown here.

Do not kill the emulator from outside. The disk image is written in
place, so a hard kill can leave it half written.

Note that with no video MAME does not act on a termination signal at
all, which is why stop.lua exists: it watches for a sentinel file and
calls manager.machine:exit(), and that is what --terminal uses.


--------------------------------------------------------------------
6. IF THE MACHINE MISBEHAVES
--------------------------------------------------------------------

$GENIX_WORK/run/mame.log has the emulator's own output.

To see inside a disk image without booting it:

    python3 tools/s5fs.py $GENIX_WORK/disk/dc1.img
    python3 tools/s5extract.py $GENIX_WORK/disk/dc1.img /tmp/out

To follow what the kernel is doing, turn on the translation log in
src/devices/machine/ns32082.cpp, run with -log, and feed the result
to tools/trace.py together with the kernel: it turns the log back
into an execution trace against the kernel's own symbols.
