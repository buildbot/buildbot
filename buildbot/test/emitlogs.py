#! /usr/bin/python

import os, sys, time

log2 = open("log2", "wt")
log3 = open("log3", "wt")

for i in range(3):
    sys.stdout.write("this is stdout %d\n" % i)
    log2.write("this is log2 %d\n" % i)
    log3.write("this is log3 %d\n" % i)
    time.sleep(1)

log2.close()
log3.close()

sys.exit(0)

