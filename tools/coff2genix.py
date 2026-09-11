#!/usr/bin/env python3
"""Convert an ns32000 System V COFF executable into the GENIX a.out that
the SYS16 ROM monitor knows how to boot.

This is a transcription of 5toG.c from the GENIX V.2 standalone sources
(stand/ns32000/5toG.c), which is exactly what National shipped for the job.

    coff2genix.py unixsys32 vmunix
"""
import struct
import sys

ZMAGIC = 0o413
NS32K_COFF = 0x0154

FILEHDR = '<HHIIIHH'          # magic nscns timdat symptr nsyms opthdr flags
AOUTHDR = '<hhiiiiiiiihH'     # ns32000 flavour, 40 bytes
SCNHSZ = 48                   # ns32000 flavour: 40 plus s_symptr/s_modno/pad


def main():
    src, dst = sys.argv[1], sys.argv[2]
    d = open(src, 'rb').read()

    magic, nscns, timdat, symptr, nsyms, opthdr, flags = struct.unpack_from(FILEHDR, d, 0)
    if magic != NS32K_COFF:
        sys.exit(f'{src}: not ns32000 COFF (magic 0x{magic:04x})')
    if opthdr != 40:
        sys.exit(f'{src}: unexpected optional header size {opthdr}')

    (amagic, vstamp, tsize, dsize, bsize, msize, mod_start,
     entry, text_start, data_start, entry_mod, aflags) = struct.unpack_from(AOUTHDR, d, 20)
    if amagic != ZMAGIC:
        sys.exit(f'{src}: bad magic 0o{amagic:o}')

    sections = {}
    for i in range(nscns):
        off = 20 + opthdr + i * SCNHSZ
        name, paddr, vaddr, size, scnptr = struct.unpack_from('<8siiii', d, off)
        sections[name.rstrip(b'\0').decode()] = (paddr, size, scnptr)

    text_paddr, text_size, text_ptr = sections['.text']
    data_paddr, data_size, data_ptr = sections['.data']
    bss_size = sections['.bss'][1]

    # 5toG rounds the text up to 512 bytes, but the ROM loader puts the
    # data straight after the text instead of at a_dat_addr, so pad to
    # exactly where the data was linked
    a_text = data_paddr - text_paddr
    if a_text < text_size:
        sys.exit('data section overlaps the text')

    exec_hdr = struct.pack(
        '<15I',
        ZMAGIC,      # a_magic
        a_text,      # a_text
        data_size,   # a_data
        bss_size,    # a_bss
        0,           # a_syms
        entry,       # a_entry
        0,           # a_entry_mod
        0,           # a_trsize
        0,           # a_drsize
        0x20,        # a_mod        (as 5toG.c sets it)
        0,           # a_link
        0,           # a_strings
        text_paddr,  # a_text_addr
        0,           # a_mod_addr
        data_paddr)  # a_dat_addr

    out = bytearray(exec_hdr.ljust(1024, b'\0'))
    out += d[text_ptr:text_ptr + text_size].ljust(a_text, b'\0')
    out += d[data_ptr:data_ptr + data_size]

    open(dst, 'wb').write(out)
    print(f'{dst}: text {text_size} (padded {a_text}) at 0x{text_paddr:06x}, '
          f'data {data_size} at 0x{data_paddr:06x}, bss {bss_size}, '
          f'entry 0x{entry:06x}, {len(out)} bytes')


if __name__ == '__main__':
    main()
