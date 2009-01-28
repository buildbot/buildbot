#! /usr/bin/python

# This is a script which delivers Change events from Mercurial to the
# buildmaster each time a changeset is pushed into a repository. Add it to
# the 'incoming' commit hook on your canonical "central" repository, by
# putting something like the following in the .hg/hgrc file of that
# repository:
#
#  [hooks]
#  incoming.buildbot = /PATH/TO/hg_buildbot.py BUILDMASTER:PORT
#
# Note that both Buildbot and Mercurial must be installed on the repository
# machine.

import os
import sys
import commands

from StringIO import StringIO
from buildbot.scripts import runner

MASTER = sys.argv[1]

CHANGESET_ID = os.environ["HG_NODE"]

# TODO: consider doing 'import mercurial.hg' and extract this information
# using the native python
out = commands.getoutput(
    "hg log -r %s --template '{author}\n{files}\n{desc}'" % CHANGESET_ID)

s = StringIO(out)
user = s.readline().strip()
# NOTE: this fail when filenames contain spaces. I cannot find a way to get
# hg to use some other filename separator.
files = s.readline().strip().split()
comments = "".join(s.readlines())

change = {
    'master': MASTER,
    # note: this is more likely to be a full email address, which would make
    # the left-hand "Changes" column kind of wide. The buildmaster should
    # probably be improved to display an abbreviation of the username.
    'username': user,
    'revision': CHANGESET_ID,
    'comments': comments,
    'files': files,
}

runner.sendchange(change, True)
