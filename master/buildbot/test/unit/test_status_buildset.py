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

from buildbot.status.buildset import BuildSetSummaryNotifierMixin
from buildbot.process.results import SUCCESS
from buildbot.test.fake import fakedb
from buildbot.test.fake import fakemaster
from buildbot.test.fake.fakebuild import FakeBuildStatus
from mock import Mock
from twisted.trial import unittest


class TestBuildSetSummaryNotifierMixin(unittest.TestCase):

    def run_fake_build(self, notifier, info=None):
        notifier.master = fakemaster.make_master()
        notifier.master_status = notifier.master.status

        builders = []
        builds = []

        for i in [0, 1, 2]:
            builder = Mock()
            build = FakeBuildStatus()

            builder.getBuild.return_value = build
            builder.name = "Builder%d" % i

            build.results = SUCCESS
            build.finished = True
            build.reason = "testReason"
            build.getBuilder.return_value = builder

            builders.append(builder)
            builds.append(build)

        def fakeGetBuilder(buildername):
            return {"Builder0": builders[0], "Builder1": builders[1], "Builder2": builders[2]}[buildername]

        notifier.master_status.getBuilder = fakeGetBuilder

        notifier.master.db.insertTestData([
            fakedb.Master(id=92),
            fakedb.Buildslave(id=13, name='sl'),
            fakedb.Buildset(id=99, results=SUCCESS, reason="testReason"),
            fakedb.Builder(id=80, name='Builder0'),
            fakedb.Builder(id=81, name='Builder1'),
            fakedb.Builder(id=82, name='Builder2'),
            fakedb.BuildRequest(id=10, buildsetid=99, builderid=80),
            fakedb.Build(number=0, buildrequestid=10, masterid=92, buildslaveid=13),
            fakedb.BuildRequest(id=11, buildsetid=99, builderid=81),
            fakedb.Build(number=0, buildrequestid=11, masterid=92, buildslaveid=13),
            fakedb.BuildRequest(id=12, buildsetid=99, builderid=82),
            fakedb.Build(number=0, buildrequestid=12, masterid=92, buildslaveid=13)
        ])

        if info is not None:
            info['bsid'] = 99
            info['builds'] = builds

        d = notifier._buildsetComplete('buildset.99.complete',
                                       {'bsid': 99, 'result': SUCCESS})
        return d

    def test_buildsetComplete_raises_notimplementederror(self):
        notifier = BuildSetSummaryNotifierMixin()
        self.assertFailure(self.run_fake_build(notifier), NotImplementedError)

    def test_buildsetComplete_calls_sendBSS(self):
        notifier = BuildSetSummaryNotifierMixin()
        fakeBSS = Mock()
        notifier.sendBuildSetSummary = fakeBSS

        info = {}

        d = self.run_fake_build(notifier, info)

        @d.addCallback
        def check(_):
            self.assertEqual(fakeBSS.call_count, 1)

            # Check that the arguments given to fakeBSS match the builds array
            # we constructed, and that the buildsetid matches. We can't easily
            # check that the buildrequest itself entirely matches, since many
            # of the fields are constructed not by us directly.
            ((buildset, builds), _) = fakeBSS.call_args
            self.assertEqual(builds, info['builds'])

            self.assertEqual(buildset['bsid'], info['bsid'])

    def test_unsub_with_no_sub(self):
        notifier = BuildSetSummaryNotifierMixin()
        notifier.summaryUnsubscribe()
