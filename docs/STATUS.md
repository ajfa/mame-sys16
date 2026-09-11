# SYS16: what works, what does not, and how it was found

## Where upstream stood

MAME's `sys16` reached its ROM monitor and stopped. Its own header recorded the
state honestly: seven of the ten power-up diagnostics failed, the serial, disk and
tape boards were `TODO`, and the machine was marked `MACHINE_NOT_WORKING`.

    p/f test                notes
     p  0 - timer
     p  1 - mmu
     p  2 - fpu             passes with firmware hack
     p  3 - cpu ram
     f  4 - emb ram
     f  5 - pio (printer)
     f  6 - gpib
     f  7 - sio board
     f  8 - tape subsystem
     f  9 - disk subsystem

## Where it stands now

Boots GENIX V.2 from the Winchester to a single user shell on the console, and
runs it: programs execute, the terminal behaves, and writes survive a shutdown and
a reboot.

Still missing, and listed in the driver header as well:

- the tape control unit at `0xd00200`
- the eight line serial board at `0xa00000`, hence no extra terminals and no
  multiuser mode
- the printer interface and the GPIB talker

The power-up diagnostics for those boards fail, as they should. They are switched
off by default in the machine configuration, because they take about a hundred
emulated seconds and test hardware that is not there.

## The disk control unit

Emulated at the level of its command interface. Three argument bytes go to
`chan00`, `chan01` and `chan02` at `0xd00000`, an opcode to `chan03` starts the
command, and a status byte is polled at `+8`. `DC_START` carries the address of an
IOCB in main memory which names the transfer and points at a table of physical
page addresses, one long per 512 byte sector.

The real board is an INS8039 driving two AM2901 bit slices from microcode in RAM.
That microcode was never dumped. The command interface, on the other hand, is
described twice in the surviving sources, by two independent drivers written two
years apart, which is enough to model it exactly:

- System V R2: `uts/ns32000/sys/dcu.h`, `io/dc.c`, `stand/ns32000/dcusaio.c`
- GENIX 1: `src/sys/dev/dcu.c`, `src/sys/stand/dcusaio.c`, `dcutest.c`

The drive shape comes from the disktab in sector 0 of the pack, the same place the
disk driver reads it at open time, so any drive from National's table works without
a recompile.

## The four things that had to be found out

### 1. The memory is not optional

With the 1.25 MB of a base machine and one extended memory board, the kernel runs
out of free pages during startup, takes the sleeping path in `memreserve()` and
touches `u.u_procp` before the u area is mapped. That aborts, and the abort handler
aborts in turn, which is a double fault. It needs the full 4 MB.

### 2. Half a kilobyte of padding

This one cost the most. `5toG.c`, the converter National shipped for turning a
System V COFF kernel into the a.out its ROM can boot, rounds the text up to a 512
byte boundary. The kernel's own linker directive aligns the data group on `0x400`,
and the ROM loader lays the data down immediately after the text rather than at
`a_dat_addr`. So the data section landed 512 bytes low, every kernel variable read
somebody else's bytes, `mktables` computed an absurd first free page, `freemem`
went negative and the first allocation aborted.

The fix is to pad the text to `a_dat_addr - a_text_addr` instead. `tools/coff2genix.py`
does that and says so.

### 3. The interrupts are not where you would guess

`icuinit` in `uts/ns32000/ml/trap.s` programs the interrupt controller with
`ELTG = 0xcbe5` and `TPL = 0x2040`. Reading those out:

- line 3, the disk, is **edge triggered on the falling edge**
- line 9, console receive, is **level triggered, active low**
- line 10, console transmit, is **edge triggered, falling**

MAME's `scn2651` drives TxRDY and RxRDY active high while the real pins are active
low, so those two need inverting. None of this shows up while the ROM monitor is
driving the disk, because the monitor polls; the kernel sleeps and waits, and that
is exactly where the boot stopped, after reading the superblock.

### 4. The configuration file is not the configuration

`cf/unixsys32.d` says the root is minor 10 and swap minor 11. The `conf.c` that was
actually compiled into the kernel says `rootdev = makedev(0, 8)` and
`swapdev = makedev(0, 9)`, that is unit 1 partitions 0 and 1, which is also what
the ROM monitor's `k` command boots. The `.d` file describes a different machine.
Read the `conf.c`.

## How it was debugged

There is no debugger for a machine like this, so two instruments did the work.

The NS32082 translation log, turned on in `ns32082.cpp`, records every instruction
fetch as an address space 0 access at level 0. `tools/trace.py` turns that log back
into an execution trace and maps it onto the kernel's own symbol table with
`tools/nm32.py`. That is what showed the abort handler re-entering itself, and then
which routine had faulted and on what address.

The second is MAME's Lua interface. `emu.register_periodic` is the callback that
actually runs on a machine with no screen; the frame notifier almost never fires.
Reading the kernel's own variables out of physical memory at the moment it failed
is what turned "it hangs" into `firstfree = 2700355`, and that number is what led
to the padding.

## Things worth knowing about the emulator

`-video none` does not stop MAME from opening the display server: its OSD layer
connects anyway and can put a window on the desktop. Taking `DISPLAY` and
`WAYLAND_DISPLAY` away from it is what actually makes it headless.

With no video it also does not act on `SIGTERM` or `SIGINT`. The only clean way to
stop it is from inside, with a Lua script watching for a sentinel file and calling
`manager.machine:exit()`, which flushes and closes the disk images. `pack/stop.lua`
does that.
