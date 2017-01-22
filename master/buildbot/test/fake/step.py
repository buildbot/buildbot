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

from twisted.internet import defer

from buildbot.process.buildstep import BuildStep
from buildbot.process.results import CANCELLED


class BuildStepController(object):

    """
    A controller for ``ControllableBuildStep``.

    https://glyph.twistedmatrix.com/2015/05/separate-your-fakes-and-your-inspectors.html
    """

    def __init__(self, **kwargs):
        self.step = ControllableBuildStep(self, **kwargs)
        self.running = False
        self.auto_finish_results = None

    def finish_step(self, result):
        assert self.running
        self.running = False
        d, self._run_deferred = self._run_deferred, None
        d.callback(result)

    def auto_finish_step(self, result):
        self.auto_finish_results = result
        if self.running:
            self.finish_step(result)


class ControllableBuildStep(BuildStep):

    """
    A latent worker that can be controlled by tests.
    """
    name = "controllableStep"

    def __init__(self, controller):
        BuildStep.__init__(self)
        self._controller = controller

    def run(self):
        if self._controller.auto_finish_results is not None:
            return defer.succeed(self._controller.auto_finish_results)
        assert not self._controller.running
        self._controller.running = True
        self._controller._run_deferred = defer.Deferred()
        return self._controller._run_deferred

    def interrupt(self, reason):
        self._controller.finish_step(CANCELLED)
