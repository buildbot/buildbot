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

import mock
from twisted.trial import unittest

from buildbot.steps.source import oldsource

class SlaveSource(unittest.TestCase):

    def doCommandCompleteTest(self,
            cmdHasGotRevision=True,
            cmdGotRevision='rev',
            initialPropertyValue=None,
            expectedPropertyValue=None,
            expectSetProperty=True):

        # set up a step with getProperty and setProperty
        step = oldsource.SlaveSource(codebase='foo')
        def getProperty(prop, default=None):
            self.assert_(prop == 'got_revision')
            if initialPropertyValue is None:
                return default
            return initialPropertyValue
        step.getProperty = getProperty

        def setProperty(prop, value, source):
            raise RuntimeError("should not be calling setProperty directly")
        step.setProperty = setProperty

        def updateSourceProperty(prop, value):
            self.failUnlessEqual((prop, value),
                    ('got_revision', expectedPropertyValue))
            self.propSet = True
        step.updateSourceProperty = updateSourceProperty

        # fake RemoteCommand, optionally with a got_revision update
        cmd = mock.Mock()
        cmd.updates = dict()
        if cmdHasGotRevision:
            cmd.updates['got_revision'] = [ cmdGotRevision ]

        # run the method and ensure it set something; the set asserts the
        # value is correct
        self.propSet = False
        step.commandComplete(cmd)
        self.assertEqual(self.propSet, expectSetProperty)

    def test_commandComplete_got_revision(self):
        self.doCommandCompleteTest(
                expectedPropertyValue='rev')

    def test_commandComplete_no_got_revision(self):
        self.doCommandCompleteTest(
                cmdHasGotRevision=False,
                expectSetProperty=False)

    def test_commandComplete_None_got_revision(self):
        self.doCommandCompleteTest(
                cmdGotRevision=None,
                expectSetProperty=False)

