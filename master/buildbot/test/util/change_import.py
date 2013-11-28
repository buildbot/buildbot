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

from __future__ import with_statement

import cPickle
import os
import shutil

from buildbot.test.util import db

from buildbot.changes.changes import Change
from buildbot.changes.changes import OldChangeMaster


class ChangeImportMixin(db.RealDatabaseMixin):

    """
    We have a number of tests that examine the results of importing particular
    flavors of Change objects.  This class uses some pickling to make this easy
    to test.

    This is a subclass of RealDatabaseMixin, so do not inherit from that class
    separately!
    """

    # on postgres, at least, many of these tests can take longer than the default
    # 120s (!!)
    timeout = 240

    def make_pickle(self, *changes, **kwargs):
        recode_fn = kwargs.pop('recode_fn', None)
        cm = OldChangeMaster()
        cm.changes = changes
        if recode_fn:
            recode_fn(cm)
        with open(self.changes_pickle, "wb") as f:
            cPickle.dump(cm, f)

    def make_change(self, **kwargs):
        return Change(**kwargs)

    def setUpChangeImport(self):
        self.basedir = os.path.abspath("basedir")
        if os.path.exists(self.basedir):
            shutil.rmtree(self.basedir)
        os.makedirs(self.basedir)
        self.changes_pickle = os.path.join(self.basedir, "changes.pck")
        return self.setUpRealDatabase()

    def tearDownChangeImport(self):
        d = self.tearDownRealDatabase()

        def rmtree(_):
            if os.path.exists(self.basedir):
                shutil.rmtree(self.basedir)
        d.addCallback(rmtree)
        return d
