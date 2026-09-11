# National Semiconductor SYS16 driver for MAME: booting GENIX

A MAME driver for the National Semiconductor SYS16, the 1983 NS16000 development
system, brought up far enough to boot **GENIX V.2**, National's port of AT&T UNIX
System V Release 2 to the Series 32000, from its own Winchester to an interactive
shell on the console.

The upstream driver reached its ROM monitor and stopped there. Seven of its ten
power-up diagnostics failed, the disk and tape boards were `TODO`, there was no
memory beyond the 256 KB on the processor board, and no interrupt reached the
processor from anything but the timer.

```
Boot: dc(1,0)vmunix
97280+7568+69888

UNIX/2.0v1: unixsys32
real mem  = 4194304
avail mem = 3867648

Copyright (c) 1984 AT&T Technologies, Inc.
        All Rights Reserved

INIT: SINGLE USER MODE
# /bin/ls /
bin  dev  etc  lib  mnt  tmp  usr  vmunix
#
```

## What you need

This repository contains **no ROM images, no kernel and no UNIX binaries**. It is
code and documentation. You supply:

- the `sys16` romset: the ten EPROMs of the Rev. 3.4 monitor and the two of the
  disk board firmware, as dumped in MAME
- the System V R2 source release for the Series 32000, for `unixsys32`, the
  kernel National shipped already linked
- the Opus5 distribution floppies, for a userland: see **Where a userland comes
  from** below

Everything here builds against MAME 0.289.

## Quick start

    export GENIX_WORK=$HOME/genix          # working directory: build, disks, logs
    pack/build.sh                          # fetch MAME 0.289 and build the driver
    tools/mkroot.sh <dist> <tree> <kernel> # assemble a root filesystem tree
    tools/mkdisk.py $GENIX_WORK/dc1.img    # a pack with a header and partitions
    tools/mkfs.py ...                      # put the tree on it
    pack/run.sh                            # boot it

`pack/README.txt` has the detail, including how to shut the machine down without
leaving the disk half written.

## State

Boots GENIX V.2 to a single user shell on the console and runs it. Typing works,
programs run, and what you write to the disk is there next time.

Not emulated, so not usable from GENIX:

- the tape control unit at `0xd00200`
- the eight line serial board at `0xa00000`, so no extra terminals and therefore
  no multiuser mode
- the printer interface and the GPIB talker

The disk board is emulated at the level of its command interface rather than its
hardware. The real board is an INS8039 driving a pair of AM2901 bit slices from
microcode held in RAM, and that microcode was never dumped, so a gate level model
is not possible from what survives. The command interface, on the other hand, is
documented twice over in the surviving sources, which is what this follows.

`docs/STATUS.md` has what works, what does not, and the four things that had to be
found out along the way.

## Layout

    docs/STATUS.md      what works, what does not, and how it was found
    docs/USING-GENIX.md where the software is, and using the machine
    patch/              the driver, as a file and as patches against MAME 0.289
    tools/              disk, filesystem and executable tools for this machine
    pack/               build and run scripts for Ubuntu

## Using it

[`docs/USING-GENIX.md`](docs/USING-GENIX.md) has the other half: links to where
each piece of software is preserved, why the userland is a hybrid and what that
means, what the machine is like once the shell is up, the two numbers that have
to be right, and shutting down.

## Where a userland comes from

Worth knowing before you start: the GENIX archives that survive hold only `/usr`.
Neither of them has a `/bin` or an `/etc` at all, so there is no GENIX `sh`, no
`ls` and no `init` anywhere to be had. A GENIX kernel on its own reaches the point
of executing `/etc/init` and can go no further.

What does work is the Opus5 distribution, preserved at bitsavers: Opus Systems'
port of the same AT&T System V Release 2 to the same ns32k COFF, for their
coprocessor board. Its binaries run correctly on National's kernel. They are not
National's binaries, and a system built this way is a hybrid; it is, as far as is
known, the only way to get a running GENIX userland today.

## Sources

The interface of every board here was read out of the surviving sources rather
than guessed:

- `uts/ns32000/sys/dcu.h`, `sys/disk.h` and `io/dc.c` from the System V R2 source
  release for the Series 32000
- `stand/ns32000/dcusaio.c` and `dcutest.c`, the standalone disk driver and its
  diagnostic, from the same release
- `src/sys/dev/dcu.c` and `src/sys/stand/dcusize.c` from the earlier 4.1BSD
  derived GENIX, which document the same boards independently
- `uts/ns32000/ml/trap.s`, which is where the interrupt controller is programmed
  and therefore where the trigger and polarity of every line is stated

All of it is preserved at bitsavers.

## Licence

BSD-3-Clause, the same as MAME. See `LICENSE`.

GENIX and Series 32000 are National Semiconductor. UNIX is AT&T. Opus5 is Opus
Systems. Nothing belonging to any of them is redistributed here.
