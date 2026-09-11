#!/usr/bin/env python3
"""List, or look up, symbols in an ns32000 COFF executable.

The ns32000 flavour of struct syment (head/syms.h) is 20 bytes: the usual
18 plus n_env and a pad byte.

    nm32.py unixsys32              list every text symbol, by address
    nm32.py unixsys32 0xb71        name the routine containing an address
"""
import struct
import sys

SYMESZ = 20
C_EXT, C_STAT = 2, 3


def symbols(path):
    d = open(path, 'rb').read()
    magic, nscns, timdat, symptr, nsyms, opthdr, flags = struct.unpack_from('<HHIIIHH', d, 0)
    strtab_off = symptr + nsyms * SYMESZ
    strtab = d[strtab_off:]

    out = []
    i = 0
    while i < nsyms:
        off = symptr + i * SYMESZ
        raw = d[off:off + SYMESZ]
        zeroes, stroff = struct.unpack_from('<II', raw, 0)
        if zeroes == 0:
            end = strtab.find(b'\0', stroff)
            name = strtab[stroff:end].decode('latin1')
        else:
            name = raw[0:8].rstrip(b'\0').decode('latin1')
        value, scnum, typ, sclass, numaux = struct.unpack_from('<IhHBB', raw, 8)
        if sclass in (C_EXT, C_STAT) and scnum > 0:
            out.append((value, name, scnum))
        i += 1 + numaux
    out.sort()
    return out


def main():
    path = sys.argv[1]
    syms = symbols(path)
    if len(sys.argv) < 3:
        for value, name, scnum in syms:
            print(f'{value:08x} {scnum} {name}')
        return
    for arg in sys.argv[2:]:
        addr = int(arg, 0)
        best = None
        for value, name, scnum in syms:
            if value <= addr:
                best = (value, name)
            else:
                break
        if best:
            print(f'{addr:#08x} is {best[1]}+{addr - best[0]:#x} (at {best[0]:#08x})')
        else:
            print(f'{addr:#08x}: below the first symbol')


if __name__ == '__main__':
    main()
