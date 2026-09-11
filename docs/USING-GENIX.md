# Getting the software, and using GENIX once it boots

Where each piece comes from, and what the machine is like to sit in front of.
The engineering side, and the four things that had to be found out, are in
[docs/STATUS.md](STATUS.md).

## Where the software is

Everything below is preserved at bitsavers. None of it is redistributed here.

| what | where |
| --- | --- |
| the GENIX archives | <https://bitsavers.org/bits/NationalSemiconductor/NS32000/Genix/> |
| Opus Systems floppies, which is where a userland comes from | <https://bitsavers.org/bits/OpusSystems/Floppies/Opus_Systems_Floppies.zip> |
| Opus Systems cpio archives, same collection | <https://bitsavers.org/bits/OpusSystems/> |

The `sys16` ROM set is the one MAME already carries for this machine: ten
EPROMs of the Rev. 3.4 monitor plus two for the disk board firmware.

The System V R2 source release for the Series 32000 is what supplies
`unixsys32`, the kernel National shipped already linked, along with the board
documentation this driver was written from. It is not one of the files listed
above and this document does not claim a URL for it; look for the Series 32000
System V release rather than for GENIX itself.

Note bitsavers refuses directory listings to anything that does not look like a
browser, so if a script of yours gets a 403 there, that is why.

## Why the userland is a hybrid, and what it means for you

Worth understanding before you judge what you are looking at. The surviving
GENIX archives hold only `/usr`. There is no `/bin` and no `/etc` in either of
them, anywhere: no GENIX `sh`, no `ls`, no `init`. A GENIX kernel on its own
reaches the point of executing `/etc/init` and stops there for good.

What fills the gap is the Opus5 distribution: Opus Systems' port of the same
AT&T System V Release 2 to the same ns32k COFF, for their coprocessor board.
Those binaries run correctly on National's kernel. So the system you boot is
National's kernel with Opus's userland. It is a hybrid, it is not what shipped
on anyone's desk in 1985, and as far as is known it is the only way to have a
running GENIX userland today.

## What the machine is like

It boots to single user and hands you a shell:

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

You are root, there is no login, and the prompt is `#`. Typing works, commands
run one at a time, programs execute, and what you write to the disk is there on
the next boot. `echo`, `/bin/find / -print` and `/bin/stty` were the first three
things run on it.

Call programs by their full path if something is not found: this is a System V
R2 shell with a spare environment, not a modern login session.

**There is no multiuser mode**, and that is a hardware gap rather than a
software one. Multiuser needs terminals, terminals need the eight line serial
board at `0xa00000`, and that board is not emulated. Nor are the tape control
unit at `0xd00200`, the printer interface or the GPIB talker.

## Two numbers that matter

**Four megabytes of memory, all of it.** With 1.25 MB the kernel runs out of
pages and aborts. The upstream driver had nothing beyond the 256 KB on the
processor board.

**`rootdev` is `makedev(0,8)`**, which is unit 1, partition 0, so the boot line
is `dc(1,0)vmunix`. The `.d` file says 10 and is wrong; `cf/conf.c` is right.
That one cost a while.

## Shutting down

`pack/README.txt` has the sequence, and it matters for the same reason it
matters on any UNIX of this age: the disk is mounted and written lazily, so
stopping the emulator underneath a running kernel leaves the filesystem dirty.
