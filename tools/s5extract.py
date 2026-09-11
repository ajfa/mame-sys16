#!/usr/bin/env python3
"""Extract the files out of a System V filesystem image into a directory.

    s5extract.py image outdir
"""
import os
import stat as st
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from s5fs import S5


def main():
    img, out = sys.argv[1], sys.argv[2]
    fs = S5(img)
    os.makedirs(out, exist_ok=True)
    for path, ino, i in fs.walk():
        target = os.path.join(out, path.lstrip('/'))
        mode = i['mode']
        if st.S_ISDIR(mode):
            os.makedirs(target, exist_ok=True)
        elif st.S_ISREG(mode):
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, 'wb') as f:
                f.write(fs.data(i))
            if mode & 0o111:
                os.chmod(target, 0o755)
            print(f'{path} {i["size"]}')
        else:
            dev = i['blk'][0]
            print(f'{path} special major {dev >> 8} minor {dev & 0xff}')


if __name__ == '__main__':
    main()
