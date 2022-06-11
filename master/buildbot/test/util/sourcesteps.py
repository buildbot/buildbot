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

from buildbot.test.steps import TestBuildStepMixin


class SourceStepMixin(TestBuildStepMixin):

    """
    Support for testing source steps.  Aside from the capabilities of
    L{TestBuildStepMixin}, this adds:

     - fake sourcestamps

    The following instance variables are available after C{setupSourceStep}, in
    addition to those made available by L{TestBuildStepMixin}:

    @ivar sourcestamp: fake SourceStamp for the build
    """

    def setUpSourceStep(self):
        return super().setup_test_build_step()

    def tearDownSourceStep(self):
        return super().tear_down_test_build_step()

    # utilities

    def setup_step(self, step, args=None, patch=None, **kwargs):
        """
        Set up C{step} for testing.  This calls L{TestBuildStepMixin}'s C{setup_step}
        and then does setup specific to a Source step.
        """
        step = super().setup_step(step, **kwargs)

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
