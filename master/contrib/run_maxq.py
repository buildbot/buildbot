#!/usr/bin/env jython

from __future__ import print_function

import glob
import sys

testdir = sys.argv[1]

orderfiles = glob.glob(testdir + '/*.tests')

# wee. just be glad I didn't make this one gigantic nested listcomp.
# anyway, this builds a once-nested list of files to test.

# open!
files = [open(fn) for fn in orderfiles]

# create prelim list of lists of files!
files = [f.readlines() for f in files]

# shwack newlines and filter out empties!
files = [filter(None, [fn.strip() for fn in fs]) for fs in files]

# prefix with testdir
files = [[testdir + '/' + fn.strip() for fn in fs] for fs in files]

print("Will run these tests:", files)

i = 0

for testlist in files:

    print("===========================")
    print("running tests from testlist", orderfiles[i])
    print("---------------------------")
    i = i + 1

    for test in testlist:
        print("running test", test)

        try:
            exec(open(test).read(), globals().copy())

        except Exception:
            ei = sys.exc_info()
            print("TEST FAILURE:", ei[1])

        else:
            print("SUCCESS")
