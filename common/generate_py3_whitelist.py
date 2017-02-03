from __future__ import absolute_import
from __future__ import print_function

import io
import re
import subprocess
import sys
import time


def addTestAndParents(set, test):
    set.add(test)
    if "." in test:
        addTestAndParents(set, test.rsplit(".", 1)[0])


test_re = re.compile("(.*) \.\.\. (.*)\n")
failing = set()
passing = set()
proc = subprocess.Popen(["trial", "--reporter=bwverbose", "buildbot"],
                        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
lasttime = int(time.time())
for line in io.TextIOWrapper(proc.stdout, encoding="utf-8"):  # or another encoding
    sys.stdout.write("passing: {} failing: {}\r".format(len(passing), len(failing)))
    res = test_re.match(line)
    if res is not None:
        test = res.group(1)
        # only count the full suite to pass (not individual tests)
        test = test.rsplit(".", 1)[0]
        passed = res.group(2) in ("[OK]", "[SKIPPED]")
        if passed:
            addTestAndParents(passing, test)
        else:
            addTestAndParents(failing, test)

# passing is is now the list of tests that have all their children passing,
# sorted, so that the parents are first
passing = sorted(passing - failing)
previous = "___noatest"
with open(".py3_tests_status.txt", 'w') as f:
    for test in passing:
        # we only write the tests that don't have their parent passing
        if not test.startswith(previous):
            previous = test
            f.write(test + "\n")
