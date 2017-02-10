from __future__ import absolute_import
from __future__ import print_function

import subprocess
import sys

from twisted.scripts import trial

with open(".py3.notworking.txt", "r") as f:
    not_working_list = f.read().splitlines()

# Get a list of all the tests by using "trial -n"
trial_output = subprocess.check_output(
                   "trial -n --reporter=bwverbose buildbot.test | "
                   "awk '/OK/ {print $1}'", shell=True)
trial_output = trial_output.decode("utf-8")
tests = trial_output.splitlines()

# Filter out the tests which are not working
for test in not_working_list:
    try:
        tests.remove(test)
    except ValueError as e:
        print("FAILED TO REMOVE ", test, type(test))

print("\n\nRunning tests with:\n\n", sys.version, "\n\n")

# Run the tests.  To avoid "Argument list too long"
# errors, invoke twisted.scripts.trial.run() directly
# instead of invoking the trial script.
sys.argv[0] = "trial"
sys.argv.append("--reporter=bwverbose")
sys.argv += tests

sys.exit(trial.run())
