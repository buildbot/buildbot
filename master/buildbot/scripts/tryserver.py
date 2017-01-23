# This file is part of Buildbot.  Buildbot is free software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, version 2.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Copyright Buildbot Team Members

from __future__ import absolute_import
from __future__ import print_function

import os
import sys
import time
from hashlib import md5

from buildbot.util import unicode2bytes


def tryserver(config):
    jobdir = os.path.expanduser(config["jobdir"])
    job = sys.stdin.read()
    # now do a 'safecat'-style write to jobdir/tmp, then move atomically to
    # jobdir/new . Rather than come up with a unique name randomly, I'm just
    # going to MD5 the contents and prepend a timestamp.
    timestring = "%d" % time.time()
    m = md5()
    job = unicode2bytes(job)
    m.update(job)
    jobhash = m.hexdigest()
    fn = "%s-%s" % (timestring, jobhash)
    tmpfile = os.path.join(jobdir, "tmp", fn)
    newfile = os.path.join(jobdir, "new", fn)
    with open(tmpfile, "wb") as f:
        f.write(job)
    os.rename(tmpfile, newfile)

    return 0
