#!/usr/bin/env python3
"""Build a System V (s5fs) filesystem image for GENIX, 1024-byte blocks.

Everything here was read off the GENIX sources and checked against the
Opus5 root floppy, which is the same filesystem written by the period tools:

  superblock   uts/ns32000/sys/filsys.h, 512 bytes at byte offset 512
               (SUPERBOFF), s_magic 0xfd187e20, s_type 2 = 1024-byte blocks
  inode        uts/ns32000/sys/ino.h, 64 bytes, 16 per block, i-list starts
               at block 2, s_isize is the number of the first data block
  directory    uts/sys/dir.h, 16 bytes: ushort d_ino then 14 name bytes
  free list    uts/sys/fblk.h, int df_nfree then 50 daddr_t, chained exactly
               the way alloc()/free() in os/alloc.c walk it

Usage:
    mkfs.py <out.img> <blocks> <root-dir> [--spec <file>] [--disktab]

The spec file adds things a host directory cannot express, one per line:

    dir   <path> <mode>
    blk   <path> <mode> <major> <minor>
    chr   <path> <mode> <major> <minor>
    link  <path> <target-path>
"""
import os
import struct
import sys
import time

BSIZE = 1024
INOPB = 16
NICFREE = 50
NICINOD = 100
SUPERBOFF = 512
ROOTINO = 2
FsMAGIC = 0xfd187e20
Fs2b = 2
DIRSIZ = 14

S_IFDIR = 0o040000
S_IFCHR = 0o020000
S_IFBLK = 0o060000
S_IFREG = 0o100000

NADDR = 13          # 10 direct, single, double, triple
NINDIR = BSIZE // 4


class Inode:
    def __init__(self, num, mode, uid=0, gid=0):
        self.num = num
        self.mode = mode
        self.nlink = 1
        self.uid = uid
        self.gid = gid
        self.size = 0
        self.addr = [0] * NADDR


class Fs:
    def __init__(self, nblocks, ninodes):
        self.nblocks = nblocks
        self.iblocks = (ninodes + INOPB - 1) // INOPB
        self.first_data = 2 + self.iblocks
        self.ninodes = self.iblocks * INOPB
        self.data = bytearray(nblocks * BSIZE)
        self.next_block = self.first_data
        self.inodes = {}
        self.next_ino = 2
        self.now = int(time.mktime((1985, 4, 10, 12, 0, 0, 0, 0, 0)))

    # --- raw blocks -----------------------------------------------------
    def put(self, blk, buf):
        assert len(buf) <= BSIZE
        off = blk * BSIZE
        self.data[off:off + len(buf)] = buf

    def alloc_block(self):
        if self.next_block >= self.nblocks:
            sys.exit('image full: raise the block count')
        b = self.next_block
        self.next_block += 1
        return b

    # --- inodes ---------------------------------------------------------
    def alloc_inode(self, mode, uid=0, gid=0):
        n = self.next_ino
        self.next_ino += 1
        if n >= self.ninodes:
            sys.exit('out of inodes')
        ino = Inode(n, mode, uid, gid)
        self.inodes[n] = ino
        return ino

    def store_data(self, ino, content):
        ino.size = len(content)
        nblk = (len(content) + BSIZE - 1) // BSIZE
        blocks = []
        for i in range(nblk):
            b = self.alloc_block()
            self.put(b, content[i * BSIZE:(i + 1) * BSIZE])
            blocks.append(b)

        # ten direct
        for i, b in enumerate(blocks[:10]):
            ino.addr[i] = b
        rest = blocks[10:]
        if not rest:
            return

        # single indirect
        first = rest[:NINDIR]
        ib = self.alloc_block()
        self.put(ib, b''.join(struct.pack('<I', x) for x in first))
        ino.addr[10] = ib
        rest = rest[NINDIR:]
        if not rest:
            return

        # double indirect
        outer = []
        while rest:
            chunk = rest[:NINDIR]
            rest = rest[NINDIR:]
            b = self.alloc_block()
            self.put(b, b''.join(struct.pack('<I', x) for x in chunk))
            outer.append(b)
            if len(outer) > NINDIR:
                sys.exit('file needs triple indirection; not implemented')
        db = self.alloc_block()
        self.put(db, b''.join(struct.pack('<I', x) for x in outer))
        ino.addr[11] = db

    def pack_inode(self, ino):
        addr = bytearray(40)
        for i, a in enumerate(ino.addr):
            addr[i * 3 + 0] = a & 0xff
            addr[i * 3 + 1] = (a >> 8) & 0xff
            addr[i * 3 + 2] = (a >> 16) & 0xff
        return (struct.pack('<HhHHI', ino.mode, ino.nlink, ino.uid, ino.gid, ino.size)
                + bytes(addr)
                + struct.pack('<III', self.now, self.now, self.now))

    def write_inodes(self):
        for n in range(1, self.ninodes + 1):
            ino = self.inodes.get(n)
            blob = self.pack_inode(ino) if ino else bytes(64)
            off = 2 * BSIZE + (n - 1) * 64
            self.data[off:off + 64] = blob

    # --- directories ----------------------------------------------------
    @staticmethod
    def dirent(num, name):
        nm = name.encode('latin1')
        if len(nm) > DIRSIZ:
            sys.exit('name too long: ' + name)
        return struct.pack('<H', num) + nm.ljust(DIRSIZ, b'\0')

    # --- free list ------------------------------------------------------
    def build_free_list(self):
        self.nfree = 0
        self.free = [0] * NICFREE
        self.tfree = 0

        def bfree(bno):
            if self.nfree == NICFREE:
                buf = struct.pack('<i', self.nfree)
                buf += b''.join(struct.pack('<I', x) for x in self.free)
                self.put(bno, buf.ljust(BSIZE, b'\0'))
                self.nfree = 0
            self.free[self.nfree] = bno
            self.nfree += 1

        bfree(0)                        # the entry that terminates the walk
        for b in range(self.nblocks - 1, self.next_block - 1, -1):
            bfree(b)
            self.tfree += 1

    def write_superblock(self):
        free_ino = [n for n in range(self.next_ino, self.ninodes + 1)][:NICINOD]
        sb = bytearray(512)
        struct.pack_into('<H', sb, 0, self.iblocks + 2)      # s_isize
        struct.pack_into('<I', sb, 4, self.nblocks)          # s_fsize
        struct.pack_into('<h', sb, 8, self.nfree)            # s_nfree
        for i, b in enumerate(self.free):
            struct.pack_into('<I', sb, 12 + i * 4, b)        # s_free[50]
        struct.pack_into('<h', sb, 212, len(free_ino))       # s_ninode
        for i, n in enumerate(free_ino):
            struct.pack_into('<H', sb, 214 + i * 2, n)       # s_inode[100]
        struct.pack_into('<I', sb, 420, self.now)            # s_time
        struct.pack_into('<I', sb, 432, self.tfree)          # s_tfree
        struct.pack_into('<H', sb, 436, self.ninodes - self.next_ino + 1)
        sb[438:444] = b'root'.ljust(6, b'\0')                # s_fname
        sb[444:450] = b'genix'.ljust(6, b'\0')               # s_fpack
        struct.pack_into('<I', sb, 504, FsMAGIC)
        struct.pack_into('<I', sb, 508, Fs2b)
        self.data[SUPERBOFF:SUPERBOFF + 512] = sb


def build(fs, srcdir, spec):
    """Walk the host tree, then apply the spec lines, then write it all out."""
    root = fs.alloc_inode(S_IFDIR | 0o755)
    assert root.num == ROOTINO
    dirs = {'/': root}
    entries = {'/': [(root.num, '.'), (root.num, '..')]}
    root.nlink = 2

    def getdir(path):
        if path in dirs:
            return dirs[path]
        parent_path = path.rsplit('/', 1)[0] or '/'
        parent = getdir(parent_path)
        d = fs.alloc_inode(S_IFDIR | 0o755)
        d.nlink = 2
        dirs[path] = d
        entries[path] = [(d.num, '.'), (parent.num, '..')]
        entries[parent_path].append((d.num, path.rsplit('/', 1)[1]))
        parent.nlink += 1
        return d

    if srcdir and os.path.isdir(srcdir):
        for dirpath, dirnames, filenames in os.walk(srcdir):
            rel = os.path.relpath(dirpath, srcdir).replace(os.sep, '/')
            here = '/' if rel == '.' else '/' + rel
            getdir(here)
            for name in sorted(filenames):
                full = os.path.join(dirpath, name)
                if os.path.islink(full):
                    continue
                with open(full, 'rb') as f:
                    content = f.read()
                mode = S_IFREG | (0o755 if os.access(full, os.X_OK) else 0o644)
                ino = fs.alloc_inode(mode)
                fs.store_data(ino, content)
                entries[here].append((ino.num, name))

    for line in spec:
        line = line.split('#')[0].strip()
        if not line:
            continue
        parts = line.split()
        kind, path = parts[0], parts[1]
        parent_path = path.rsplit('/', 1)[0] or '/'
        name = path.rsplit('/', 1)[1]
        if kind == 'dir':
            getdir(path)
            dirs[path].mode = S_IFDIR | int(parts[2], 8)
            continue
        getdir(parent_path)
        if kind == 'link':
            target = parts[2]
            tino = None
            for num, nm in entries[target.rsplit('/', 1)[0] or '/']:
                if nm == target.rsplit('/', 1)[1]:
                    tino = num
            if tino is None:
                sys.exit('link target not found: ' + target)
            entries[parent_path].append((tino, name))
            fs.inodes[tino].nlink += 1
            continue
        mode = int(parts[2], 8) | (S_IFBLK if kind == 'blk' else S_IFCHR)
        ino = fs.alloc_inode(mode)
        dev = (int(parts[3]) << 8) | int(parts[4])
        ino.addr[0] = dev
        entries[parent_path].append((ino.num, name))

    # directories become ordinary files holding 16-byte entries
    for path, ents in entries.items():
        blob = b''.join(Fs.dirent(n, nm) for n, nm in ents)
        fs.store_data(dirs[path], blob)

    fs.write_inodes()
    fs.build_free_list()
    fs.write_superblock()


def main():
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    out, nblocks, srcdir = sys.argv[1], int(sys.argv[2]), sys.argv[3]
    spec = []
    disktab = False
    args = sys.argv[4:]
    while args:
        a = args.pop(0)
        if a == '--spec':
            spec = open(args.pop(0)).read().splitlines()
        elif a == '--disktab':
            disktab = True

    # roughly one inode per 8 KB, which is generous for this system and
    # cheap: the whole i-list is a few hundred blocks
    ninodes = max(512, (nblocks // 8 + 15) // 16 * 16)
    fs = Fs(nblocks, ninodes)
    build(fs, srcdir, spec)

    if disktab:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import mkdisk
        fs.data[0:92] = mkdisk.disktab()

    with open(out, 'wb') as f:
        f.write(fs.data)
    print(f'{out}: {nblocks} blocks of {BSIZE}, i-list blocks 2..{fs.iblocks + 1}, '
          f'first data block {fs.first_data}, {fs.next_block - fs.first_data} used, '
          f'{fs.tfree} free, {fs.next_ino - 1} inodes used of {fs.ninodes}')


if __name__ == '__main__':
    main()
