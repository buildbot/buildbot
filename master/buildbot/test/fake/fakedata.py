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
import types
from twisted.internet import defer
from buildbot.data import connector

class FakeUpdates(object):

    # unlike "real" update methods, all of the fake methods are here in a
    # single class.

    def __init__(self, master, testcase):
        self.master = master
        self.testcase = testcase

    # test cases should assert the value of this list.  Changes are numbered
    # starting at 1.
    changesAdded = []

    def addChange(self, files=None, comments=None, author=None,
            revision=None, when_timestamp=None, branch=None, category=None,
            revlink='', properties={}, repository='', codebase=None,
            project='', src=None):
        # double-check args, types, etc.
        if 0:
            # TODO...
            self.testcase.assertIsInstance(files, list)
            for f in files:
                self.testcase.assertIsInstance(f, unicode)
            self.testcase.assertIsInstance(comments, (types.NoneType, unicode))
            self.testcase.assertIsInstance(author, (types.NoneType, unicode))
            self.testcase.assertIsInstance(revision, (types.NoneType, unicode))
            self.testcase.assertIsInstance(when_timestamp, (types.NoneType, int))
            self.testcase.assertIsInstance(branch, (types.NoneType, unicode))
            self.testcase.assertIsInstance(category, (types.NoneType, unicode))
            self.testcase.assertIsInstance(revlink, (types.NoneType, unicode))
            self.testcase.assertIsInstance(properties, dict)
            for k, v in properties.iteritems():
                self.testcase.assertIsInstance(k, unicode)
                # v needs to be json-able; no need to check that here
            self.testcase.assertIsInstance(repository, unicode)
            self.testcase.assertIsInstance(codebase, unicode)
            self.testcase.assertIsInstance(project, unicode)
            self.testcase.assertIsInstance(src, (types.NoneType, unicode))

        # ensure we get all of the args and don't forget if more are added
        if not self.changesAdded:
            self.changesAdded = []
        self.changesAdded.append(locals())
        self.changesAdded[-1].pop('self')
        return defer.succeed(len(self.changesAdded))

    def assertChangesAdded(self, expected):
        self.assertEqual

class FakeDataConnector(connector.DataConnector):
    # FakeDataConnector inherits from DataConnector so it can get all of the
    # proper getter behavior; it overrides all of the relevant updates with
    # fake methods, though.

    def __init__(self, master, testcase):
        self.master = master
        self.updates = FakeUpdates(master, testcase)

        # get, startConsuming, and control are delegated to a real connector,
        # after some additional assertions
        self.realConnector = connector.DataConnector(master)

    def get(self, options, path):
        if not isinstance(path, tuple):
            raise TypeError('path must be a tuple')
        return self.realConnector.get(options, path)

    def startConsuming(self, callback, options, path):
        if not isinstance(path, tuple):
            raise TypeError('path must be a tuple')
        return self.realConnector.startConsuming(callback, options, path)

    def control(self, action, args, path):
        if not isinstance(path, tuple):
            raise TypeError('path must be a tuple')
        return self.realConnector.control(action, args, path)
