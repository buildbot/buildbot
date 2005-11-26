#! /usr/bin/python

import os, sys

sys.stdout.write("this is stdout\n")
sys.stderr.write("this is stderr\n")
if os.environ.has_key("EMIT_TEST"):
    sys.stdout.write("EMIT_TEST: %s\n" % os.environ["EMIT_TEST"])
rc = int(sys.argv[1])
sys.exit(rc)
