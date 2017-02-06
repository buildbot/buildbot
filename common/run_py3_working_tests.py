from __future__ import absolute_import
from __future__ import print_function

import subprocess
import sys


def chunks(l, n):
    """Yield successive n-sized chunks from l."""
    # Code example taken from:
    #    http://stackoverflow.com/questions/312443/how-do-you-split-a-list-into-evenly-sized-chunks
    for i in range(0, len(l), n):
        yield l[i:i + n]

with open(".py3.notworking.txt", "r") as f:
    blacklist = f.read().splitlines()

# Get a list of all the tests by using "trial -n"
trial_output = subprocess.check_output(
                   "trial -n --reporter=bwverbose buildbot.test | "
                   "awk '/OK/ {print $1}'", shell=True)
trial_output = trial_output.decode("utf-8")
tests = trial_output.splitlines()

# Filter out the blacklisted tests
for test in blacklist:
    try:
        tests.remove(test)
    except ValueError as e:
        print("FAILED TO REMOVE ", test, type(test))

# Run the tests.  To avoid "Argument list too long"
# errors, pass only 300 tests at a time to the argv of
# trial.
foundErrors = False
defaultEncoding = sys.getfilesystemencoding()
errorOutput = ""
for testChunk in chunks(tests, 300):
    try:
        output = subprocess.check_output(["trial",
                                          "--reporter=bwverbose"]
                                         + testChunk,
                                         stderr=subprocess.STDOUT)
        print(output.decode(defaultEncoding))
    except subprocess.CalledProcessError as e:
        output = e.output.decode(defaultEncoding)
        print(output)
        errorOutput += output
        foundErrors = True

if foundErrors:
    print(errorOutput)
    print("\n\n!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
    print("FAILED: check full build log for errors")
    print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n")

sys.exit(foundErrors)
