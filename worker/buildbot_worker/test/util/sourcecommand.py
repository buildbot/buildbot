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

from buildbot_worker.test.util import command


class SourceCommandTestMixin(command.CommandTestMixin):

    """
    Support for testing Source Commands; an extension of CommandTestMixin
    """

    def make_command(self, cmdclass, args, makedirs=False, initial_sourcedata=''):
        """
        Same as the parent class method, but this also adds some source-specific
        patches:

        * writeSourcedata - writes to self.sourcedata (self is the TestCase)
        * readSourcedata - reads from self.sourcedata
        * doClobber - invokes RunProcess(['clobber', DIRECTORY])
        * doCopy - invokes RunProcess(['copy', cmd.srcdir, cmd.workdir])
        """

        cmd = command.CommandTestMixin.make_command(self, cmdclass, args, makedirs)

        # note that these patches are to an *instance*, not a class, so there
        # is no need to use self.patch() to reverse them

        self.sourcedata = initial_sourcedata

        def readSourcedata():
            if self.sourcedata is None:
                raise IOError("File not found")
            return self.sourcedata
        cmd.readSourcedata = readSourcedata

        def writeSourcedata(res):
            self.sourcedata = cmd.sourcedata
            return res
        cmd.writeSourcedata = writeSourcedata

    def check_sourcedata(self, _, expected_sourcedata):
        """
        Assert that the sourcedata (from the patched functions - see
        make_command) is correct.  Use this as a deferred callback.
        """
        self.assertEqual(self.sourcedata, expected_sourcedata)
        return _
