#!/usr/bin/env python3
"""Turn the NS32082 translation log into an execution trace.

Every instruction fetch shows up as an access_level 0 translation, so the
sequence of distinct fetch addresses before an abort is the path the kernel
took.  Map those to kernel symbols to get the call chain.

    trace.py error.log unixsys32 [steps] [--first]

By default it reports the last abort in the log, which is the one that kills
the machine; --first reports the first, which is usually one of the monitor's
own diagnostics.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from nm32 import symbols

RE_XLATE = re.compile(r'translate address_space 0 access_level (\d+) .* address 0x([0-9a-f]+)')
RE_ABORT = re.compile(r'translate level \d abort eia 0x([0-9a-f]+)')


def name_of(syms, addr):
    if addr >= 0x100000:
        return 'outside the kernel'
    best = None
    for value, name, scnum in syms:
        if value <= addr:
            best = (value, name)
        else:
            break
    return f'{best[1]}+0x{addr - best[0]:x}' if best else '?'


def main():
    log, kernel = sys.argv[1], sys.argv[2]
    steps = int(sys.argv[3]) if len(sys.argv) > 3 and not sys.argv[3].startswith('-') else 60
    first = '--first' in sys.argv
    syms = symbols(kernel)

    lines = open(log, errors='replace').read().splitlines()

    idx = None
    for i, line in enumerate(lines):
        if RE_ABORT.search(line):
            idx = i
            if first:
                break
    if idx is None:
        sys.exit('no abort in the log')

    abort_at = int(RE_ABORT.search(lines[idx]).group(1), 16)
    print(f'abort on 0x{abort_at:06x} ({name_of(syms, abort_at)}) at log line {idx + 1}')

    fetches = []
    for line in lines[:idx]:
        m = RE_XLATE.search(line)
        if m and int(m.group(1)) == 0:
            fetches.append(int(m.group(2), 16))

    ins = []
    for a in fetches:
        if ins and 0 <= a - ins[-1] <= 8:
            continue
        ins.append(a)

    print(f'\nlast {steps} instruction addresses before it:')
    for a in ins[-steps:]:
        print(f'  {a:06x}  {name_of(syms, a)}')


if __name__ == '__main__':
    main()
