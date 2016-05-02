from twisted.internet import defer
from twisted.trial import unittest

from buildbot.test.util.config import ConfigErrorsMixin
from mock import Mock
from mock import patch

from buildbot.process.results import FAILURE
from buildbot.process.results import SUCCESS
from buildbot.reporters.syslogreporter import SyslogStatusPush
from buildbot.reporters import utils
from buildbot.test.fake import fakedb
from buildbot.test.fake import fakemaster
import syslog


class TestSyslogStatusPush(ConfigErrorsMixin, unittest.TestCase):

    def setUp(self):
        self.master = fakemaster.make_master(testcase=self, wantData=True,
                                             wantDb=True, wantMq=True)

    @defer.inlineCallbacks
    def setupBuildResults(self, results, wantPreviousBuild=False):
        # this testsuite always goes through setupBuildResults so that
        # the data is sure to be the real data schema known coming from data api

        self.db = self.master.db
        self.db.insertTestData([
            fakedb.Master(id=92),
            fakedb.Worker(id=13, name='sl'),
            fakedb.Buildset(id=98, results=results, reason="testReason1"),
            fakedb.Builder(id=80, name='Builder1'),
            fakedb.BuildRequest(id=11, buildsetid=98, builderid=80),
            fakedb.Build(id=20, number=0, builderid=80, buildrequestid=11, workerid=13,
                         masterid=92, results=results),
            fakedb.Step(id=50, buildid=20, number=5, name='make'),
            fakedb.BuildsetSourceStamp(buildsetid=98, sourcestampid=234),
            fakedb.SourceStamp(id=234, patchid=99),
            fakedb.Change(changeid=13, branch=u'trunk', revision=u'9283', author='me@foo',
                          repository=u'svn://...', codebase=u'cbsvn',
                          project=u'world-domination', sourcestampid=234),
            fakedb.Log(id=60, stepid=50, name='stdio', slug='stdio', type='s',
                       num_lines=7),
            fakedb.LogChunk(logid=60, first_line=0, last_line=1, compressed=0,
                            content=u'Unicode log with non-ascii (\u00E5\u00E4\u00F6).'),
            fakedb.Patch(id=99, patch_base64='aGVsbG8sIHdvcmxk',
                         patch_author='him@foo', patch_comment='foo', subdir='/foo',
                         patchlevel=3),
            fakedb.Tag(id=35, name='tag1'),
            fakedb.BuildersTags(id=36, builderid=80, tagid=35)
        ])
        for _id in (20,):
            self.db.insertTestData([
                fakedb.BuildProperty(buildid=_id, name="workername", value="sl"),
                fakedb.BuildProperty(buildid=_id, name="reason", value="because"),
            ])
        res = yield utils.getDetailsForBuildset(self.master, 98, wantProperties=True,
                                                wantPreviousBuild=wantPreviousBuild)
        builds = res['builds']
        buildset = res['buildset']

        @defer.inlineCallbacks
        def getChangesForBuild(buildid):
            assert buildid == 20
            ch = yield self.master.db.changes.getChange(13)
            defer.returnValue([ch])

        self.master.db.changes.getChangesForBuild = getChangesForBuild
        defer.returnValue((buildset, builds))

    @defer.inlineCallbacks
    def setupSyslogStatusPush(self, *args, **kwargs):
        ssp = SyslogStatusPush(*args, **kwargs)
        yield ssp.setServiceParent(self.master)
        yield ssp.startService()
        defer.returnValue(ssp)

    @patch('syslog.syslog')
    @patch('syslog.openlog')
    @defer.inlineCallbacks
    def test_default_success_message(self, mock_openlog, mock_syslog):
        _, builds = yield self.setupBuildResults(SUCCESS)
        ssp = yield self.setupSyslogStatusPush()
        yield ssp.buildMessage(builds, SUCCESS)
        mock_openlog.assert_called_with('buildbot')
        mock_syslog.assert_called_with(syslog.LOG_INFO, str(builds))

    @patch('syslog.syslog')
    @patch('syslog.openlog')
    @defer.inlineCallbacks
    def test_default_failure_message(self, mock_openlog, mock_syslog):
        _, builds = yield self.setupBuildResults(FAILURE)
        ssp = yield self.setupSyslogStatusPush()
        yield ssp.buildMessage(builds, FAILURE)
        mock_openlog.assert_called_with('buildbot')
        mock_syslog.assert_called_with(syslog.LOG_INFO, str(builds))

    def test_enforces_log_severity(self):
        self.assertRaisesConfigError("Please provide a valid log severity",
                                     lambda: SyslogStatusPush(cancelledSeverity=-10))

    def test_enforces_builders_tags_exclusivity(self):
        self.assertRaisesConfigError("Please specify only builders or tags to" +
                                     " include - not both.",
                                     lambda: SyslogStatusPush(tags=["tag1",
                                                                    "tag2"],
                                                              builders=["builder1",
                                                                        "builder2"]))

    @defer.inlineCallbacks
    def test_buildsetsummary_message(self):
        _, builds = yield self.setupBuildResults(SUCCESS)
        result = yield utils.getDetailsForBuildset(
            self.master, bsid=98,
            wantProperties=True,
            wantSteps=True,
            wantLogs=True)
        builds = result['builds']
        ssp = yield self.setupSyslogStatusPush(buildSetSummary=True)
        ssp.buildMessage = Mock()
        yield ssp.buildsetComplete('buildset.98.complete', dict(bsid=98))
        ssp.buildMessage.assert_called_with(builds, SUCCESS)

    @defer.inlineCallbacks
    def test_build_is_needed_with_builders(self):
        _, builds = yield self.setupBuildResults(SUCCESS)
        ssp = yield self.setupSyslogStatusPush(builders=['Builder1'])
        ssp.buildMessage = Mock()
        for build in builds:
            self.assertEquals(True, ssp.isBuildNeeded(build))
            yield ssp.buildComplete('buildrequest', build)
            ssp.buildMessage.assert_called_with(build, SUCCESS)

    @defer.inlineCallbacks
    def test_build_isnt_needed_with_builders(self):
        _, builds = yield self.setupBuildResults(SUCCESS)
        ssp = yield self.setupSyslogStatusPush(builders=['No-Builder'])
        ssp.buildMessage = Mock()
        for build in builds:
            self.assertEqual(False, ssp.isBuildNeeded(build))
            yield ssp.buildComplete('buildrequest', build)
            ssp.buildMessage.assert_not_called()

    @defer.inlineCallbacks
    def test_build_is_needed_with_tags(self):
        _, builds = yield self.setupBuildResults(SUCCESS)
        ssp = yield self.setupSyslogStatusPush(tags=['tag1'])
        ssp.buildMessage = Mock()
        for build in builds:
            self.assertEqual(True, ssp.isBuildNeeded(build))
            yield ssp.buildComplete('buildrequest', build)
            ssp.buildMessage.assert_called_with(build, SUCCESS)

    @defer.inlineCallbacks
    def test_build_isnt_needed_with_tags(self):
        _, builds = yield self.setupBuildResults(SUCCESS)
        ssp = yield self.setupSyslogStatusPush(tags=['no-tag'])
        ssp.buildMessage = Mock()
        for build in builds:
            self.assertEqual(False, ssp.isBuildNeeded(build))
            yield ssp.buildComplete('buildrequest', build)
            ssp.buildMessage.assert_not_called()
