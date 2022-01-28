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


import json
import os

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.data import connector as dataconnector
from buildbot.data.graphql import GraphQLConnector
from buildbot.mq import connector as mqconnector
from buildbot.process.results import SUCCESS
from buildbot.schedulers.forcesched import ForceScheduler
from buildbot.test import fakedb
from buildbot.test.fake import fakemaster
from buildbot.test.reactor import TestReactorMixin
from buildbot.util import toJson

try:
    from ruamel.yaml import YAML
except ImportError:
    YAML = None


try:
    import graphql as graphql_core
except ImportError:
    graphql_core = None


class GraphQL(unittest.TestCase, TestReactorMixin):
    if not graphql_core:
        skip = "graphql-core is required for GraphQL integration tests"

    master = None

    def load_yaml(self, f):
        if YAML is None:
            # for running the test ruamel is not needed (to avoid a build dependency for distros)
            import yaml
            return yaml.safe_load(f)
        self.yaml = YAML()
        self.yaml.default_flow_style = False
        # default is round-trip
        return self.yaml.load(f)

    def save_yaml(self, data, f):
        if YAML is None:
            raise ImportError("please install ruamel.yaml for test regeneration")
        self.yaml.dump(data, f)

    @defer.inlineCallbacks
    def setUp(self):
        self.setup_test_reactor(use_asyncio=True)

        master = fakemaster.make_master(self)
        master.db = fakedb.FakeDBConnector(self)
        yield master.db.setServiceParent(master)

        master.config.mq = {'type': "simple"}
        master.mq = mqconnector.MQConnector()
        yield master.mq.setServiceParent(master)
        yield master.mq.setup()

        master.data = dataconnector.DataConnector()
        yield master.data.setServiceParent(master)

        master.graphql = GraphQLConnector()
        yield master.graphql.setServiceParent(master)

        master.config.www = {'graphql': {"debug": True}}
        master.graphql.reconfigServiceWithBuildbotConfig(master.config)

        self.master = master
        scheds = [ForceScheduler(
            name="force",
            builderNames=["runtests0", "runtests1", "runtests2", "slowruntests"])]
        self.master.allSchedulers = lambda: scheds

        yield self.master.startService()

        yield self.insert_initial_data()

    @defer.inlineCallbacks
    def tearDown(self):
        yield self.master.stopService()

    def insert_initial_data(self):
        self.master.db.insertTestData([
            fakedb.Master(id=1),
            fakedb.Worker(id=1, name='example-worker'),

            fakedb.Scheduler(id=1, name='custom', enabled=1),
            fakedb.Scheduler(id=2, name='all', enabled=2),
            fakedb.Scheduler(id=3, name='force', enabled=3),

            fakedb.SchedulerMaster(schedulerid=1, masterid=1),
            fakedb.SchedulerMaster(schedulerid=2, masterid=1),
            fakedb.SchedulerMaster(schedulerid=3, masterid=1),

            fakedb.Builder(id=1, name='runtests1'),
            fakedb.Builder(id=2, name='runtests2'),
            fakedb.Builder(id=3, name='runtests3'),

            fakedb.BuilderMaster(id=1, builderid=1, masterid=1),
            fakedb.BuilderMaster(id=2, builderid=2, masterid=1),
            fakedb.BuilderMaster(id=3, builderid=3, masterid=1),

            fakedb.Tag(id=1, name='tag1'),
            fakedb.Tag(id=2, name='tag12'),
            fakedb.Tag(id=3, name='tag23'),

            fakedb.BuildersTags(id=1, builderid=1, tagid=1),
            fakedb.BuildersTags(id=2, builderid=1, tagid=2),
            fakedb.BuildersTags(id=3, builderid=2, tagid=2),
            fakedb.BuildersTags(id=4, builderid=2, tagid=3),
            fakedb.BuildersTags(id=5, builderid=3, tagid=3),

            fakedb.Buildset(id=1, results=SUCCESS, reason="Force reason 1",
                            submitted_at=100000, complete_at=100110, complete=1),
            fakedb.Buildset(id=2, results=SUCCESS, reason="Force reason 2",
                            submitted_at=100200, complete_at=100330, complete=1),
            fakedb.Buildset(id=3, results=SUCCESS, reason="Force reason 3",
                            submitted_at=100400, complete_at=100550, complete=1),

            fakedb.BuildsetProperty(buildsetid=1, property_name='scheduler',
                                    property_value='["custom", "Scheduler"]'),
            fakedb.BuildsetProperty(buildsetid=2, property_name='scheduler',
                                    property_value='["all", "Scheduler"]'),
            fakedb.BuildsetProperty(buildsetid=3, property_name='scheduler',
                                    property_value='["force", "Scheduler"]'),
            fakedb.BuildsetProperty(buildsetid=3, property_name='owner',
                                    property_value='["some@example.com", "Force Build Form"]'),

            fakedb.SourceStamp(id=1, branch='master', revision='1234abcd'),
            fakedb.Change(changeid=1, branch='master', revision='1234abcd', sourcestampid=1),
            fakedb.ChangeProperty(changeid=1, property_name="owner",
                                  property_value='["me@example.com", "change"]'),
            fakedb.ChangeProperty(changeid=1, property_name="other_prop",
                                  property_value='["value", "change"]'),
            fakedb.BuildsetSourceStamp(id=1, buildsetid=1, sourcestampid=1),
            fakedb.BuildsetSourceStamp(id=2, buildsetid=2, sourcestampid=1),
            fakedb.BuildsetSourceStamp(id=3, buildsetid=3, sourcestampid=1),

            fakedb.BuildRequest(id=1, buildsetid=1, builderid=1, results=SUCCESS,
                                submitted_at=100001, complete_at=100109, complete=1),
            fakedb.BuildRequest(id=2, buildsetid=2, builderid=1, results=SUCCESS,
                                submitted_at=100201, complete_at=100329, complete=1),
            fakedb.BuildRequest(id=3, buildsetid=3, builderid=2, results=SUCCESS,
                                submitted_at=100401, complete_at=100549, complete=1),

            fakedb.Build(id=1, number=1, buildrequestid=1, builderid=1, workerid=1,
                         masterid=1001, started_at=100002, complete_at=100108,
                         state_string='build successful', results=SUCCESS),
            fakedb.Build(id=2, number=2, buildrequestid=2, builderid=1, workerid=1,
                         masterid=1001, started_at=100202, complete_at=100328,
                         state_string='build successful', results=SUCCESS),
            fakedb.Build(id=3, number=1, buildrequestid=3, builderid=2, workerid=1,
                         masterid=1001, started_at=100402, complete_at=100548,
                         state_string='build successful', results=SUCCESS),

            fakedb.BuildProperty(buildid=3, name='reason', value='"force build"',
                                 source="Force Build Form"),
            fakedb.BuildProperty(buildid=3, name='owner', value='"some@example.com"',
                                 source="Force Build Form"),
            fakedb.BuildProperty(buildid=3, name='scheduler', value='"force"',
                                 source="Scheduler"),
            fakedb.BuildProperty(buildid=3, name='buildername', value='"runtests3"',
                                 source="Builder"),
            fakedb.BuildProperty(buildid=3, name='workername', value='"example-worker"',
                                 source="Worker"),

            fakedb.Step(id=1, number=1, name='step1', buildid=1,
                        started_at=100010, complete_at=100019, state_string='step1 done'),
            fakedb.Step(id=2, number=2, name='step2', buildid=1,
                        started_at=100020, complete_at=100029, state_string='step2 done'),
            fakedb.Step(id=3, number=3, name='step3', buildid=1,
                        started_at=100030, complete_at=100039, state_string='step3 done'),
            fakedb.Step(id=11, number=1, name='step1', buildid=2,
                        started_at=100210, complete_at=100219, state_string='step1 done'),
            fakedb.Step(id=12, number=2, name='step2', buildid=2,
                        started_at=100220, complete_at=100229, state_string='step2 done'),
            fakedb.Step(id=13, number=3, name='step3', buildid=2,
                        started_at=100230, complete_at=100239, state_string='step3 done'),
            fakedb.Step(id=21, number=1, name='step1', buildid=3,
                        started_at=100410, complete_at=100419, state_string='step1 done'),
            fakedb.Step(id=22, number=2, name='step2', buildid=3,
                        started_at=100420, complete_at=100429, state_string='step2 done'),
            fakedb.Step(id=23, number=3, name='step3', buildid=3,
                        started_at=100430, complete_at=100439, state_string='step3 done'),

            fakedb.Log(id=1, name='stdio', slug='stdio', stepid=1, complete=1, num_lines=10),
            fakedb.Log(id=2, name='stdio', slug='stdio', stepid=2, complete=1, num_lines=20),
            fakedb.Log(id=3, name='stdio', slug='stdio', stepid=3, complete=1, num_lines=30),
            fakedb.Log(id=11, name='stdio', slug='stdio', stepid=11, complete=1, num_lines=30),
            fakedb.Log(id=12, name='stdio', slug='stdio', stepid=12, complete=1, num_lines=40),
            fakedb.Log(id=13, name='stdio', slug='stdio', stepid=13, complete=1, num_lines=50),
            fakedb.Log(id=21, name='stdio', slug='stdio', stepid=21, complete=1, num_lines=50),
            fakedb.Log(id=22, name='stdio', slug='stdio', stepid=22, complete=1, num_lines=60),
            fakedb.Log(id=23, name='stdio', slug='stdio', stepid=23, complete=1, num_lines=70),

            fakedb.LogChunk(logid=1, first_line=0, last_line=2,
                            content='o line1\no line2\n'),
            fakedb.LogChunk(logid=1, first_line=2, last_line=3,
                            content='o line3\n'),
            fakedb.LogChunk(logid=2, first_line=0, last_line=4,
                            content='o line1\no line2\no line3\no line4\n'),
        ])

    @defer.inlineCallbacks
    def test_examples_from_yaml(self):
        """This test takes input from yaml file containing queries to execute and
        expected results. In order to ease writing of tests, if the expected key is not found,
        it is automatically generated, so developer only has to review results
        Full regen can still be done with regen local variable just below
        """
        regen = False
        need_save = False
        fn = os.path.join(os.path.dirname(__file__), "test_graphql_queries.yaml")
        with open(fn, encoding='utf-8') as f:
            data = self.load_yaml(f)
        focussed_data = [test for test in data if test.get('focus')]
        if not focussed_data:
            focussed_data = data
        for test in focussed_data:
            query = test['query']
            result = yield self.master.graphql.query(
                query
            )
            self.assertIsNone(result.errors)
            if 'expected' not in test or regen:
                need_save = True
                test['expected'] = result.data
            else:
                # remove ruamel metadata before compare (it is needed for round-trip regen,
                # but confuses the comparison)
                result_data = json.loads(json.dumps(result.data, default=toJson))
                expected = json.loads(json.dumps(test['expected'], default=toJson))
                self.assertEqual(
                    result_data, expected, f"for {query}")
        if need_save:
            with open(fn, 'w', encoding='utf-8') as f:
                self.save_yaml(data, f)

    @defer.inlineCallbacks
    def test_buildrequests_builds(self):
        data = yield self.master.graphql.query(
            "{buildrequests{buildrequestid, builds{number, buildrequestid}}}"
        )

        self.assertEqual(data.errors, None)
        for br in data.data["buildrequests"]:
            for build in br["builds"]:
                self.assertEqual(build["buildrequestid"], br["buildrequestid"])
