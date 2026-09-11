dir  /bin 0755
dir  /etc 0755
dir  /tmp 0777
dir  /usr 0755
dir  /lib 0755
dir  /dev 0755
chr  /dev/console 0622 0 0
chr  /dev/syscon  0622 0 0
chr  /dev/systty  0622 0 0
chr  /dev/tty     0666 3 0
chr  /dev/mem     0400 1 0
chr  /dev/kmem    0400 1 1
chr  /dev/null    0666 1 2
chr  /dev/error   0400 5 0
chr  /dev/lp      0666 7 0
dir  /dev/dsk 0755
blk  /dev/dsk/0s0 0600 0 0
blk  /dev/dsk/1s0 0600 0 8
blk  /dev/dsk/1s1 0600 0 9
blk  /dev/root    0600 0 8
blk  /dev/swap    0600 0 9
dir  /dev/rdsk 0755
chr  /dev/rdsk/0s0 0600 2 0
chr  /dev/rdsk/1s0 0600 2 8
chr  /dev/rmt0     0600 6 0
blk  /dev/mt0      0600 1 0
