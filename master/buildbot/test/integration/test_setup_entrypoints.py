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


from twisted.trial import unittest

from buildbot.interfaces import IBuildStep
from buildbot.interfaces import IChangeSource
from buildbot.interfaces import IScheduler
from buildbot.interfaces import IWorker
from buildbot.plugins.db import get_plugins


# NOTE: when running this test locally, make sure to reinstall master after every change to pick up
# new entry points.
class TestSetupPyEntryPoints(unittest.TestCase):
    def test_changes(self):
        get_plugins('changes', IChangeSource, load_now=True)

    def test_schedulers(self):
        get_plugins('schedulers', IScheduler, load_now=True)

    def test_steps(self):
        get_plugins('steps', IBuildStep, load_now=True)

    def test_util(self):
        get_plugins('util', None, load_now=True)

    def test_reporters(self):
        get_plugins('reporters', None, load_now=True)

    def test_secrets(self):
        get_plugins('secrets', None, load_now=True)

    def test_webhooks(self):
        get_plugins('webhooks', None, load_now=True)

    def test_workers(self):
        get_plugins('worker', IWorker, load_now=True)
