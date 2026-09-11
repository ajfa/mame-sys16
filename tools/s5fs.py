#!/usr/bin/env python3
"""Read a System V (s5fs) filesystem image, little-endian, 1024-byte blocks."""
import struct, sys, stat as st

BS = 1024
SUPERBOFF = 512

class S5:
    def __init__(self, path):
        self.d = open(path, 'rb').read()
        self.isize, self.fsize = struct.unpack_from('<H2xI', self.d, SUPERBOFF)

    def inode(self, ino):
        off = 2 * BS + (ino - 1) * 64
        e = self.d[off:off + 64]
        mode, nlink, uid, gid, size = struct.unpack_from('<HhHHI', e, 0)
        addr = e[12:12 + 39]
        blocks = [addr[i] | (addr[i+1] << 8) | (addr[i+2] << 16) for i in range(0, 39, 3)]
        return dict(mode=mode, nlink=nlink, uid=uid, gid=gid, size=size, blk=blocks)

    def blk(self, n):
        return self.d[n * BS:(n + 1) * BS] if n else b'\0' * BS

    def ind(self, n):
        b = self.blk(n)
        return [struct.unpack_from('<I', b, i)[0] for i in range(0, BS, 4)]

    def data(self, i):
        out = b''
        for n in i['blk'][:10]:
            out += self.blk(n)
        if i['blk'][10]:
            for n in self.ind(i['blk'][10]):
                out += self.blk(n)
        if i['blk'][11]:
            for m in self.ind(i['blk'][11]):
                if not m: break
                for n in self.ind(m):
                    out += self.blk(n)
        return out[:i['size']]

    def readdir(self, ino):
        i = self.inode(ino)
        d = self.data(i)
        ents = []
        for o in range(0, len(d), 16):
            n, name = struct.unpack_from('<H14s', d, o)
            if n:
                ents.append((n, name.split(b'\0')[0].decode('latin1')))
        return ents

    def walk(self, ino=2, path='', depth=0, out=None):
        if out is None: out = []
        for n, name in self.readdir(ino):
            if name in ('.', '..'): continue
            i = self.inode(n)
            p = path + '/' + name
            out.append((p, n, i))
            if st.S_ISDIR(i['mode']) and depth < 12:
                self.walk(n, p, depth + 1, out)
        return out

if __name__ == '__main__':
    fs = S5(sys.argv[1])
    print(f'isize={fs.isize} blocks  fsize={fs.fsize} blocks  ({fs.fsize*BS} bytes)')
    for p, n, i in fs.walk():
        m = i['mode']
        t = 'd' if st.S_ISDIR(m) else ('c' if (m & 0o170000) == 0o020000 else
            ('b' if (m & 0o170000) == 0o060000 else '-'))
        print(f'{t}{m & 0o7777:04o} ino={n:4d} {i["size"]:8d}  {p}')
