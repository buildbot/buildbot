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

import mock

from buildbot.test.util import steps


class SourceStepMixin(steps.BuildStepMixin):

    """
    Support for testing source steps.  Aside from the capabilities of
    L{BuildStepMixin}, this adds:

     - fake sourcestamps

    The following instance variables are available after C{setupSourceStep}, in
    addition to those made available by L{BuildStepMixin}:

    @ivar sourcestamp: fake SourceStamp for the build
    """

    def setUpSourceStep(self):
        return steps.BuildStepMixin.setUpBuildStep(self)

    def tearDownSourceStep(self):
        return steps.BuildStepMixin.tearDownBuildStep(self)

    # utilities

    def setupStep(self, step, args=None, patch=None, **kwargs):
        """
        Set up C{step} for testing.  This calls L{BuildStepMixin}'s C{setupStep}
        and then does setup specific to a Source step.
        """
        step = steps.BuildStepMixin.setupStep(self, step, **kwargs)

        if args is None:
            args = {}

        ss = self.sourcestamp = mock.Mock(name="sourcestamp")
        ss.ssid = 9123
        ss.branch = args.get('branch', None)
        ss.revision = args.get('revision', None)
        ss.project = ''
        ss.repository = ''
        ss.patch = patch
        ss.patch_info = None
        ss.changes = []
        self.build.getSourceStamp = lambda x=None: ss
        return step
