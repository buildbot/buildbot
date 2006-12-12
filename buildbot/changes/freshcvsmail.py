#! /usr/bin/python

# leftover import for compatibility

import warnings

warnings.warn("buildbot.changes.freshcvsmail is deprecated as of 0.7.6 . Please import buildbot.changes.mail.FCMaildirSource instead. This compatibility import will be removed in 0.7.7",
              DeprecationWarning)

from buildbot.changes.mail import FCMaildirSource
