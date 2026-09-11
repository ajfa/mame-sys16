#!/usr/bin/env python3
"""Build a SYS16 Winchester image: the disk header that the GENIX disk
driver reads out of sector 0, plus room for the partitions.

The header layout is struct disktab from uts/ns32000/sys/disk.h:

    long  dt_magic      0x6d737000
    short dt_ploz       formatting data, sector zero
    short dt_plonz      formatting data, other sectors
    short dt_nsec       sectors per track
    short dt_ntr        tracks per cylinder
    short dt_ncyl       cylinders per unit
    short dt_spcyl      sectors per cylinder
    long  dt_spunit     sectors per unit
    struct { int nbl; int cyloff; } dt_part[8]
    char  dt_name[8]

The drive types are National's own, from the table in the standalone
sources (stand/dcusize.c).  The emulated controller reads this header to
learn the drive's shape, exactly as the disk driver does at open time, so
changing the type here is all it takes.

    mkdisk.py out.img [type]
"""
import struct
import sys

SECTOR = 512
DMAGIC = 0x6d737000

# name: sectors per track, tracks per cylinder, cylinders, ploz, plonz
DRIVES = {
    'basf20':  (24, 3, 614, 11, 17),
    '3m20':    (30, 4, 280, 29, 57),
    '3m60':    (32, 4, 838,  9, 21),
    'imi20':   (18, 5, 388, 29, 61),
    'imi60':   (18, 7, 776, 29, 61),
    'priam70': (22, 5, 1049, 23, 73),
}

DEFAULT = 'priam70'


def layout(drive):
    nsec, ntr, ncyl, ploz, plonz = DRIVES[drive]
    spcyl = nsec * ntr
    spunit = spcyl * ncyl

    # The kernel roots on minor 8 (unit 1, partition 0) and swaps on minor 9
    # (partition 1, 5040 blocks from the start of it), which is what
    # uts/ns32000/cf/conf.c in the source release says.  Leave the root
    # everything but the tail of the pack, and put swap in that tail.
    swap_cyls = max(46, (5040 + spcyl - 1) // spcyl + 1)
    root_cyls = ncyl - swap_cyls

    part = [
        (root_cyls * spcyl, 0),
        (swap_cyls * spcyl, root_cyls),
        (root_cyls * spcyl, 0),
        (swap_cyls * spcyl, root_cyls),
        (spunit, 0),
        (0, 0), (0, 0), (0, 0),
    ]
    return nsec, ntr, ncyl, spcyl, spunit, ploz, plonz, part


def disktab(drive=DEFAULT, name=None):
    nsec, ntr, ncyl, spcyl, spunit, ploz, plonz, part = layout(drive)
    b = struct.pack('<IhhhhhhI', DMAGIC, ploz, plonz, nsec, ntr, ncyl, spcyl, spunit)
    for nbl, cyloff in part:
        b += struct.pack('<ii', nbl, cyloff)
    b += (name or drive).encode()[:8].ljust(8, b'\0')
    assert len(b) == 92, len(b)
    return b


def root_blocks(drive=DEFAULT):
    """How many 1024-byte filesystem blocks fit in partition 0."""
    return layout(drive)[7][0][0] // 2


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else 'dc1.img'
    drive = sys.argv[2] if len(sys.argv) > 2 else DEFAULT
    if drive not in DRIVES:
        sys.exit('drive types: ' + ', '.join(DRIVES))

    nsec, ntr, ncyl, spcyl, spunit, ploz, plonz, part = layout(drive)
    with open(out, 'wb') as f:
        f.truncate(spunit * SECTOR)
        f.seek(0)
        f.write(disktab(drive).ljust(SECTOR, b'\0'))

    print(f'{out}: {drive}, {ncyl} cyl x {ntr} heads x {nsec} sec = '
          f'{spunit} sectors ({spunit * SECTOR // (1 << 20)} MB)')
    print(f'  root  partition 0: {part[0][0]} sectors at cylinder 0 '
          f'({root_blocks(drive)} blocks of 1024)')
    print(f'  swap  partition 1: {part[1][0]} sectors at cylinder {part[1][1]}')


if __name__ == '__main__':
    main()
