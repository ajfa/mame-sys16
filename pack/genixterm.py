#!/usr/bin/env python3
"""Bring up the emulated National Semiconductor SYS16 and hand its serial
console to this terminal.

The machine has no screen: its console is an RS-232 port, so MAME runs with
no video at all and the port is bridged to the terminal over a socket.  That
keeps the whole thing inside the shell, with no X server and no window.

  genixterm.py              boot GENIX and use it
  genixterm.py --check      boot it, prove it reached a shell, and stop
  genixterm.py --monitor    stop at the ROM monitor instead of booting
  genixterm.py --exec CMD   boot it, run one command, sync and stop

While GENIX is up:
  Ctrl-]  q     sync the disk and shut the machine down
  Ctrl-]  x     shut down at once, without syncing
  Ctrl-]  ]     send a literal Ctrl-] to GENIX
"""
import argparse
import errno
import fcntl
import os
import selectors
import signal
import socket
import subprocess
import sys
import termios
import time
import tty

HERE = os.path.dirname(os.path.abspath(__file__))

BANNER = b'UNIX/2.0v1'
PROMPT = b'# '
MONITOR = b'\r*'


def free_port():
    s = socket.socket()
    s.bind(('127.0.0.1', 0))
    port = s.getsockname()[1]
    s.close()
    return port


class Machine:
    """MAME, its serial console, and the typing that gets GENIX booted."""

    def __init__(self, args):
        self.args = args

        # Two machines writing the same disk image would destroy it, and the
        # damage only shows up as a kernel that loads and then dies.  Refuse
        # the second one rather than let that happen.
        self.lock = open(os.path.join(args.work, 'disk.lock'), 'w')
        try:
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            sys.exit('another session is already using this disk;\n'
                     'close it first, or copy the package if you want two.')

        self.seen = bytearray()
        self.booted = False
        self.pending = []          # bytes still to type, slowly
        self.next_key = 0.0

        self.listener = socket.socket()
        self.listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        port = free_port()
        self.listener.bind(('127.0.0.1', port))
        self.listener.listen(1)

        cmd = [
            args.mame, 'sys16',
            '-rompath', args.rompath,
            '-conport', 'null_modem',
            '-bitb', f'socket.127.0.0.1:{port}',
            '-hard1', args.disk0,
            '-hard2', args.disk1,
            '-video', 'none',
            '-sound', 'none',
            # keep everything the emulator writes inside work/
            '-nvram_directory', os.path.join(args.work, 'nvram'),
            '-cfg_directory', os.path.join(args.work, 'cfg'),
            '-snapshot_directory', os.path.join(args.work, 'snap'),
            '-diff_directory', os.path.join(args.work, 'diff'),
            '-inipath', args.work,
            # the only way to stop it cleanly: see stop.lua
            '-autoboot_script', os.path.join(HERE, 'stop.lua'),
        ]
        if args.seconds:
            cmd += ['-seconds_to_run', str(args.seconds)]

        # -video none is not enough on its own: the emulator's OSD still opens
        # a connection to whatever display server is around, and on a desktop
        # that can put a window on screen and take the keyboard focus away
        # from whatever you were doing.  Take the display away from it.
        env = dict(os.environ)
        env.pop('DISPLAY', None)
        env.pop('WAYLAND_DISPLAY', None)
        env['SDL_VIDEODRIVER'] = 'dummy'
        env['SDL_AUDIODRIVER'] = 'dummy'

        self.log = open(os.path.join(args.work, 'mame.log'), 'wb')
        self.proc = subprocess.Popen(cmd, stdout=self.log, stderr=subprocess.STDOUT,
                                     stdin=subprocess.DEVNULL, cwd=HERE, env=env)

        self.listener.settimeout(30)
        try:
            self.sock, _ = self.listener.accept()
        except socket.timeout:
            self.proc.kill()
            sys.exit('the emulator did not open its serial console; see mame.log')
        self.sock.setblocking(False)

    # --- typing ---------------------------------------------------------
    def type(self, text):
        """Queue characters to be sent one at a time, at a human rate."""
        self.pending.extend(text)

    def pump_keys(self, now):
        if self.pending and now >= self.next_key:
            ch = bytes([self.pending.pop(0)])
            try:
                self.sock.send(ch)
            except OSError:
                pass
            self.next_key = now + 0.12

    # --- output ---------------------------------------------------------
    def note(self, data):
        self.seen.extend(data)
        del self.seen[:-4096]
        if not self.booted and not self.args.monitor:
            if MONITOR in self.seen and not self.pending:
                # the monitor is up: tell it to boot dc(1,0)vmunix
                self.booted = True
                self.type(b'k\r')

    def saw(self, marker):
        return marker in self.seen

    # --- shutdown -------------------------------------------------------
    def sync_and_stop(self):
        self.type(b'\r/bin/sync\r')
        deadline = time.time() + 6
        while self.pending and time.time() < deadline:
            self.pump_keys(time.time())
            self.drain()
            time.sleep(0.02)
        time.sleep(1.5)
        self.stop()

    def drain(self):
        try:
            self.sock.recv(4096)
        except OSError:
            pass

    def stop(self):
        # The disk image is written in place, so killing the emulator while a
        # write is in flight leaves a damaged image, and the damage shows up
        # only later as a kernel that loads and then dies.  Give it room to
        # finish, and say so plainly if it has to be killed.
        if self.proc.poll() is None:
            # ask it from inside; it ignores SIGTERM and SIGINT with no video
            try:
                open(os.path.join(self.args.work, 'stop'), 'w').close()
            except OSError:
                pass
            try:
                self.proc.wait(timeout=20)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait()
                sys.stderr.write(
                    '\r\nthe emulator did not stop when asked and had to be '
                    'killed.\r\nthe disk may be damaged; if the next boot '
                    'misbehaves, run ./run-linux.sh --reset\r\n')
        try:
            self.sock.close()
        except OSError:
            pass
        self.listener.close()
        self.log.close()


def run_check(m):
    """Headless: prove the machine boots all the way to a shell."""
    deadline = time.time() + m.args.timeout
    gone = False
    while time.time() < deadline and m.proc.poll() is None:
        m.pump_keys(time.time())
        try:
            data = m.sock.recv(4096)
            if not data:
                gone = True
                break
            m.note(data)
            sys.stdout.write(data.decode('latin1'))
            sys.stdout.flush()
        except OSError as e:
            if e.errno not in (errno.EAGAIN, errno.EWOULDBLOCK):
                gone = True
                break
            time.sleep(0.02)
        if m.saw(BANNER) and m.saw(b'SINGLE USER MODE') and m.saw(PROMPT):
            break

    if gone or m.proc.poll() is not None:
        print('\nthe emulator stopped on its own; see work/mame.log')

    ok = m.saw(BANNER) and m.saw(b'SINGLE USER MODE') and m.saw(PROMPT)
    if ok:
        # Exercise it, so this proves a live shell and not just a prompt.
        # The quotes make the shell's output differ from the echo of what
        # was typed, so a match can only have come from the shell.
        m.type(b"echo ok''1234\r")
        end = time.time() + 25
        while time.time() < end and not m.saw(b'ok1234\r\n'):
            m.pump_keys(time.time())
            try:
                data = m.sock.recv(4096)
                if data:
                    m.note(data)
                    sys.stdout.write(data.decode('latin1'))
                    sys.stdout.flush()
            except OSError:
                time.sleep(0.02)
        ok = m.saw(b'ok1234\r\n')

    m.sync_and_stop()
    print()
    print('CHECK PASSED: GENIX booted to a shell and ran a command' if ok
          else 'CHECK FAILED: see mame.log')
    return 0 if ok else 1


def run_exec(m, command):
    """Boot, wait for the prompt, run one command, then shut down cleanly."""
    deadline = time.time() + m.args.timeout
    typed = False
    done = time.time() + m.args.timeout
    while time.time() < deadline and m.proc.poll() is None:
        m.pump_keys(time.time())
        try:
            data = m.sock.recv(4096)
            if data:
                m.note(data)
                sys.stdout.write(data.decode('latin1'))
                sys.stdout.flush()
        except OSError:
            time.sleep(0.02)
        if not typed and m.saw(PROMPT) and m.saw(b'SINGLE USER MODE'):
            typed = True
            m.type(command.encode('latin1') + b'\r')
            done = time.time() + 40
            m.seen.clear()
        if typed and time.time() > done:
            break
        if typed and m.seen.count(b'# ') >= 1 and not m.pending \
                and m.seen.rstrip().endswith(b'#'):
            break

    m.sync_and_stop()
    print()
    return 0 if typed else 1


def run_interactive(m):
    """Give the terminal to the machine until the user asks to leave."""
    fd = sys.stdin.fileno()
    saved = termios.tcgetattr(fd)
    sel = selectors.DefaultSelector()
    sel.register(sys.stdin, selectors.EVENT_READ)
    sel.register(m.sock, selectors.EVENT_READ)
    escape = False

    sys.stdout.write('\r\nBooting GENIX.  Ctrl-] then q to sync and shut down.\r\n')
    sys.stdout.flush()

    try:
        tty.setraw(fd)
        while m.proc.poll() is None:
            m.pump_keys(time.time())
            for key, _ in sel.select(timeout=0.05):
                if key.fileobj is sys.stdin:
                    data = os.read(fd, 1024)
                    if not data:
                        raise KeyboardInterrupt
                    for b in data:
                        if escape:
                            escape = False
                            if b in (ord('q'), ord('Q')):
                                termios.tcsetattr(fd, termios.TCSADRAIN, saved)
                                print('\r\nsyncing the disk and shutting down...')
                                m.sync_and_stop()
                                print('the machine has stopped.')
                                return 0
                            if b in (ord('x'), ord('X')):
                                termios.tcsetattr(fd, termios.TCSADRAIN, saved)
                                print('\r\nshutting down without syncing...')
                                m.stop()
                                print('the machine has stopped.')
                                return 0
                            m.pending.append(0x1d)
                        elif b == 0x1d:          # Ctrl-]
                            escape = True
                        else:
                            m.pending.append(b)
                else:
                    try:
                        data = m.sock.recv(4096)
                    except OSError:
                        data = b''
                    if not data:
                        raise KeyboardInterrupt
                    m.note(data)
                    os.write(sys.stdout.fileno(), data)
    except KeyboardInterrupt:
        pass
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, saved)
        m.stop()
    print('\r\nthe machine has stopped.')
    return 0


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--check', action='store_true', help='verify, do not interact')
    p.add_argument('--monitor', action='store_true', help='stop at the ROM monitor')
    p.add_argument('--exec', dest='command', metavar='CMD',
                   help='run one command, then sync and stop')
    p.add_argument('--mame', default=os.path.join(HERE, 'mame', 'genix'))
    p.add_argument('--rompath', default=os.path.join(HERE, 'roms'))
    p.add_argument('--disk0', default=os.path.join(HERE, 'disk', 'dc0.img'))
    p.add_argument('--disk1', default=os.path.join(HERE, 'disk', 'dc1.img'))
    p.add_argument('--work', default=os.path.join(HERE, 'work'))
    p.add_argument('--timeout', type=float, default=420.0,
                   help='give up after this many seconds (checks only)')
    p.add_argument('--seconds', type=int, default=0,
                   help='stop after this many emulated seconds')
    args = p.parse_args()

    os.makedirs(args.work, exist_ok=True)
    m = Machine(args)
    if args.check:
        return run_check(m)
    if args.command:
        return run_exec(m, args.command)
    if not sys.stdin.isatty():
        m.stop()
        sys.exit('there is no terminal here; use --check')
    return run_interactive(m)


if __name__ == '__main__':
    sys.exit(main())
