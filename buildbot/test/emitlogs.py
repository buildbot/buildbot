#! /usr/bin/python

import sys, time

log2 = open("log2.out", "wt")
log3 = open("log3.out", "wt")

def write(i):
    log2.write("this is log2 %d\n" % i)
    log2.flush()
    log3.write("this is log3 %d\n" % i)
    log3.flush()
    sys.stdout.write("this is stdout %d\n" % i)
    sys.stdout.flush()

write(0)
time.sleep(1)
write(1)
sys.stdin.read(1)
write(2)

log2.close()
log3.close()

sys.exit(0)

