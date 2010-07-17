#! /usr/bin/env python

gl = {}
execfile("../buildbot/__init__.py", gl)
version = gl['version']
print "@set VERSION", version
