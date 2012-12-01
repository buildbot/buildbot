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

from mock import Mock
from buildbot import config
from twisted.trial import unittest
from buildbot.status.results import SUCCESS, FAILURE
from buildbot.status.mail import MailNotifier
from twisted.internet import defer
from buildbot.test.fake import fakedb
from buildbot.test.fake.fakebuild import FakeBuildStatus
from buildbot.process import properties

class FakeLog(object):
    def __init__(self, text):
        self.text = text

    def getName(self):
        return 'log-name'

    def getStep(self):
        class FakeStep(object):
            def getName(self):
                return 'step-name'
        return FakeStep()

    def getText(self):
        return self.text


class TestMailNotifier(unittest.TestCase):
    def test_createEmail_message_without_patch_and_log_contains_unicode(self):
        builds = [ FakeBuildStatus(name="build") ]
        msgdict = create_msgdict()
        mn = MailNotifier('from@example.org')
        m = mn.createEmail(msgdict, u'builder-n\u00E5me', u'project-n\u00E5me',
                           SUCCESS, builds)
        try:
            m.as_string()
        except UnicodeEncodeError:
            self.fail('Failed to call as_string() on email message.')

    def test_createEmail_extraHeaders_one_build(self):
        builds = [ FakeBuildStatus(name="build") ]
        builds[0].properties = properties.Properties()
        builds[0].setProperty('hhh','vvv')
        msgdict = create_msgdict()
        mn = MailNotifier('from@example.org', extraHeaders=dict(hhh='vvv'))
        # add some Unicode to detect encoding problems
        m = mn.createEmail(msgdict, u'builder-n\u00E5me', u'project-n\u00E5me',
                           SUCCESS, builds)
        txt = m.as_string()
        self.assertIn('hhh: vvv', txt)

    def test_createEmail_extraHeaders_two_builds(self):
        builds = [ FakeBuildStatus(name="build1"),
                   FakeBuildStatus(name="build2") ]
        msgdict = create_msgdict()
        mn = MailNotifier('from@example.org', extraHeaders=dict(hhh='vvv'))
        m = mn.createEmail(msgdict, u'builder-n\u00E5me', u'project-n\u00E5me',
                           SUCCESS, builds)
        txt = m.as_string()
        # note that the headers are *not* rendered
        self.assertIn('hhh: vvv', txt)

    def test_createEmail_message_with_patch_and_log_containing_unicode(self):
        builds = [ FakeBuildStatus(name="build") ]
        msgdict = create_msgdict()
        patches = [ ['', u'\u00E5\u00E4\u00F6', ''] ]
        msg = u'Unicode log with non-ascii (\u00E5\u00E4\u00F6).'
        # add msg twice: as unicode and already encoded
        logs = [ FakeLog(msg), FakeLog(msg.encode('utf-8')) ]
        mn = MailNotifier('from@example.org', addLogs=True)
        m = mn.createEmail(msgdict, u'builder-n\u00E5me',
                           u'project-n\u00E5me', SUCCESS,
                           builds, patches, logs)
        try:
            m.as_string()
        except UnicodeEncodeError:
            self.fail('Failed to call as_string() on email message.')

    def test_createEmail_message_with_nonascii_patch(self):
        builds = [ FakeBuildStatus(name="build") ]
        msgdict = create_msgdict()
        patches = [ ['', '\x99\xaa', ''] ]
        logs = [ FakeLog('simple log') ]
        mn = MailNotifier('from@example.org', addLogs=True)
        m = mn.createEmail(msgdict, u'builder', u'pr', SUCCESS,
                           builds, patches, logs)
        txt = m.as_string()
        self.assertIn('application/octet-stream', txt)

    def test_init_enforces_categories_and_builders_are_mutually_exclusive(self):
        self.assertRaises(config.ConfigErrors,
                          MailNotifier, 'from@example.org',
                          categories=['fast','slow'], builders=['a','b'])

    def test_builderAdded_ignores_unspecified_categories(self):
        mn = MailNotifier('from@example.org', categories=['fast'])

        builder = Mock()
        builder.category = 'slow'

        self.assertEqual(None, mn.builderAdded('dummyBuilder', builder))
        self.assert_(builder not in mn.watched)

    def test_builderAdded_subscribes_to_all_builders_by_default(self):
        mn = MailNotifier('from@example.org')

        builder = Mock()
        builder.category = 'slow'
        builder2 = Mock()
        builder2.category = None

        self.assertEqual(mn, mn.builderAdded('dummyBuilder', builder))
        self.assertEqual(mn, mn.builderAdded('dummyBuilder2', builder2))
        self.assertTrue(builder in mn.watched)
        self.assertTrue(builder2 in mn.watched)

    def test_buildFinished_ignores_unspecified_builders(self):
        mn = MailNotifier('from@example.org', builders=['a','b'])

        build = FakeBuildStatus()
        build.builder = Mock()

        self.assertEqual(None, mn.buildFinished('dummyBuilder', build, SUCCESS))
        
    def test_buildsetFinished_sends_email(self):
        fakeBuildMessage = Mock()
        mn = MailNotifier('from@example.org', 
                          buildSetSummary=True, 
                          mode=("failing", "passing", "warnings"),
                          builders=["Builder"])
        
        mn.buildMessage = fakeBuildMessage
        
        def fakeGetBuild(number):
            return build
        
        def fakeGetBuilder(buildername):
            if buildername == builder.name: 
                return builder
            return None
        
        def fakeGetBuildRequests(self, bsid):
            return defer.succeed([{"buildername":"Builder", "brid":1}])
 
        builder = Mock()
        builder.getBuild = fakeGetBuild
        builder.name = "Builder"
        
        build = FakeBuildStatus()
        build.results = FAILURE
        build.finished = True
        build.reason = "testReason"
        build.getBuilder.return_value = builder
       
        self.db = fakedb.FakeDBConnector(self)
        self.db.insertTestData([fakedb.SourceStampSet(id=127),
                                fakedb.Buildset(id=99, sourcestampsetid=127,
                                                results=SUCCESS,
                                                reason="testReason"),
                                fakedb.BuildRequest(id=11, buildsetid=99,
                                                    buildername='Builder'),
                                fakedb.Build(number=0, brid=11),
                                ])
        mn.parent = self
        
        self.status = Mock()
        mn.master_status = Mock()
        mn.master_status.getBuilder = fakeGetBuilder
        mn.buildMessageDict = Mock()
        mn.buildMessageDict.return_value = {"body":"body", "type":"text",
                                            "subject":"subject"}
            
        mn.buildsetFinished(99, FAILURE)
        fakeBuildMessage.assert_called_with("Buildset Complete: testReason",
                                            [build], SUCCESS)
 

    def test_buildFinished_ignores_unspecified_categories(self):
        mn = MailNotifier('from@example.org', categories=['fast'])


        build = FakeBuildStatus(name="build")
        build.builder = Mock()
        build.builder.category = 'slow'

        self.assertEqual(None, mn.buildFinished('dummyBuilder', build, SUCCESS))

    def test_buildFinished_mode_all_always_sends_email(self):
        mock_method = Mock()
        self.patch(MailNotifier, "buildMessage", mock_method)
        mn = MailNotifier('from@example.org', mode=("failing", "passing", "warnings"))

        build = FakeBuildStatus(name="build")
        mn.buildFinished('dummyBuilder', build, FAILURE)

        mock_method.assert_called_with('dummyBuilder', [build], FAILURE)

    def test_buildFinished_mode_failing_ignores_successful_build(self):
        mn = MailNotifier('from@example.org', mode=("failing",))

        build = FakeBuildStatus(name="build")

        self.assertEqual(None, mn.buildFinished('dummyBuilder', build, SUCCESS))

    def test_buildFinished_mode_passing_ignores_failed_build(self):
        mn = MailNotifier('from@example.org', mode=("passing",))

        build = FakeBuildStatus(name="build")

        self.assertEqual(None, mn.buildFinished('dummyBuilder', build, FAILURE))

    def test_buildFinished_mode_problem_ignores_successful_build(self):
        mn = MailNotifier('from@example.org', mode=("problem",))

        build = FakeBuildStatus(name="build")

        self.assertEqual(None, mn.buildFinished('dummyBuilder', build, SUCCESS))

    def test_buildFinished_mode_problem_ignores_two_failed_builds_in_sequence(self):
        mn = MailNotifier('from@example.org', mode=("problem",))

        build = FakeBuildStatus(name="build")
        old_build = FakeBuildStatus(name="old_build")
        build.getPreviousBuild.return_value = old_build
        old_build.getResults.return_value = FAILURE

        self.assertEqual(None, mn.buildFinished('dummyBuilder', build, FAILURE))

    def test_buildFinished_mode_change_ignores_first_build(self):
        mn = MailNotifier('from@example.org', mode=("change",))

        build = FakeBuildStatus(name="build")
        build.getPreviousBuild.return_value = None

        self.assertEqual(None, mn.buildFinished('dummyBuilder', build, FAILURE))
        self.assertEqual(None, mn.buildFinished('dummyBuilder', build, SUCCESS))


    def test_buildFinished_mode_change_ignores_same_result_in_sequence(self):
        mn = MailNotifier('from@example.org', mode=("change",))

        build = FakeBuildStatus(name="build")
        old_build = FakeBuildStatus(name="old_build")
        build.getPreviousBuild.return_value = old_build
        old_build.getResults.return_value = FAILURE

        build2 = FakeBuildStatus(name="build2")
        old_build2 = FakeBuildStatus(name="old_build2")
        build2.getPreviousBuild.return_value = old_build2
        old_build2.getResults.return_value = SUCCESS

        self.assertEqual(None, mn.buildFinished('dummyBuilder', build, FAILURE))
        self.assertEqual(None, mn.buildFinished('dummyBuilder', build2, SUCCESS))

    def test_buildMessage_addLogs(self):
        mn = MailNotifier('from@example.org', mode=("change",), addLogs=True)

        mn.buildMessageDict = Mock()
        mn.buildMessageDict.return_value = {"body":"body", "type":"text",
                                            "subject":"subject"}

        mn.createEmail = Mock("createEmail")

        mn._gotRecipients = Mock("_gotReceipients")
        mn._gotRecipients.return_value = None

        mn.master_status = Mock()
        mn.master_status.getTitle.return_value = 'TITLE'

        bldr = Mock(name="builder")
        builds = [ FakeBuildStatus(name='build1'),
                   FakeBuildStatus(name='build2') ]
        logs = [ FakeLog('log1'), FakeLog('log2') ]
        for b, l in zip(builds, logs):
            b.builder = bldr
            b.results = 0
            b.getSourceStamp.return_value = ss = Mock(name='ss')
            ss.patch = None
            ss.changes = []
            b.getLogs.return_value = [ l ]
        d = mn.buildMessage("mybldr", builds, 0)
        def check(_):
            mn.createEmail.assert_called_with(
                dict(body='body\n\nbody\n\n', type='text', subject='subject'),
                'mybldr', 'TITLE', 0, builds, [], logs)
        d.addCallback(check)
        return d

    def do_test_sendToInterestedUsers(self, lookup=None, extraRecipients=[],
                                      sendToInterestedUsers=True,
                                      exp_called_with=None, exp_TO=None,
                                      exp_CC=None):
        from email.Message import Message
        m = Message()

        mn = MailNotifier(fromaddr='from@example.org',
                          lookup=lookup,
                          sendToInterestedUsers=sendToInterestedUsers,
                          extraRecipients=extraRecipients)
        mn.sendMessage = Mock()

        def fakeGetBuild(number):
            return build
        def fakeGetBuilder(buildername):
            if buildername == builder.name:
                return builder
            return None
        def fakeGetBuildRequests(self, bsid):
            return defer.succeed([{"buildername":"Builder", "brid":1}])

        builder = Mock()
        builder.getBuild = fakeGetBuild
        builder.name = "Builder"

        build = FakeBuildStatus(name="build")
        build.result = FAILURE
        build.finished = True
        build.reason = "testReason"
        build.builder = builder

        def fakeCreateEmail(msgdict, builderName, title, results, builds=None,
                            patches=None, logs=None):
            # only concerned with m['To'] and m['CC'], which are added in
            # _got_recipients later
            return m
        mn.createEmail = fakeCreateEmail

        self.db = fakedb.FakeDBConnector(self)
        self.db.insertTestData([fakedb.SourceStampSet(id=1099),
                                fakedb.Buildset(id=99, sourcestampsetid=1099,
                                                results=SUCCESS,
                                                reason="testReason"),
                                fakedb.BuildRequest(id=11, buildsetid=99,
                                                    buildername='Builder'),
                                fakedb.Build(number=0, brid=11),
                                fakedb.Change(changeid=9123),
                                fakedb.ChangeUser(changeid=9123, uid=1),
                                fakedb.User(uid=1, identifier="tdurden"),
                                fakedb.UserInfo(uid=1, attr_type='svn',
                                            attr_data="tdurden"),
                                fakedb.UserInfo(uid=1, attr_type='email',
                                            attr_data="tyler@mayhem.net")
                                ])

        # fake sourcestamp with relevant user bits
        ss = Mock(name="sourcestamp")
        fake_change = Mock(name="change")
        fake_change.number = 9123
        ss.changes = [fake_change]
        ss.patch, ss.addPatch = None, None

        def fakeGetSS():
            return ss
        build.getSourceStamp = fakeGetSS

        def _getInterestedUsers():
            # 'narrator' in this case is the owner, which tests the lookup
            return ["Big Bob <bob@mayhem.net>", "narrator"]
        build.getInterestedUsers = _getInterestedUsers

        def _getResponsibleUsers():
            return ["Big Bob <bob@mayhem.net>"]
        build.getResponsibleUsers = _getResponsibleUsers

        mn.parent = self
        self.status = mn.master_status = mn.buildMessageDict = Mock()
        mn.master_status.getBuilder = fakeGetBuilder
        mn.buildMessageDict.return_value = {"body": "body", "type": "text"}

        mn.buildMessage(builder.name, [build], build.result)
        mn.sendMessage.assert_called_with(m, exp_called_with)
        self.assertEqual(m['To'], exp_TO)
        self.assertEqual(m['CC'], exp_CC)

    def test_sendToInterestedUsers_lookup(self):
        self.do_test_sendToInterestedUsers(
                           lookup="example.org",
                           exp_called_with=['Big Bob <bob@mayhem.net>',
                                            'narrator@example.org'],
                           exp_TO="Big Bob <bob@mayhem.net>, " \
                                  "narrator@example.org")

    def test_buildMessage_sendToInterestedUsers_no_lookup(self):
        self.do_test_sendToInterestedUsers(
                                   exp_called_with=['tyler@mayhem.net'],
                                   exp_TO="tyler@mayhem.net")

    def test_buildMessage_sendToInterestedUsers_extraRecipients(self):
        self.do_test_sendToInterestedUsers(
                                   extraRecipients=["marla@mayhem.net"],
                                   exp_called_with=['tyler@mayhem.net',
                                                    'marla@mayhem.net'],
                                   exp_TO="tyler@mayhem.net",
                                   exp_CC="marla@mayhem.net")
    def test_sendToInterestedUsers_False(self):
        self.do_test_sendToInterestedUsers(
                                   extraRecipients=["marla@mayhem.net"],
                                   sendToInterestedUsers=False,
                                   exp_called_with=['marla@mayhem.net'],
                                   exp_TO="marla@mayhem.net")

    def test_sendToInterestedUsers_two_builds(self):
        from email.Message import Message
        m = Message()

        mn = MailNotifier(fromaddr="from@example.org", lookup=None)
        mn.sendMessage = Mock()

        def fakeGetBuilder(buildername):
            if buildername == builder.name:
                return builder
            return None
        def fakeGetBuildRequests(self, bsid):
            return defer.succeed([{"buildername":"Builder", "brid":1}])

        builder = Mock()
        builder.name = "Builder"

        build1 = FakeBuildStatus(name="build")
        build1.result = FAILURE
        build1.finished = True
        build1.reason = "testReason"
        build1.builder = builder

        build2 = FakeBuildStatus(name="build")
        build2.result = FAILURE
        build2.finished = True
        build2.reason = "testReason"
        build2.builder = builder

        def fakeCreateEmail(msgdict, builderName, title, results, builds=None,
                            patches=None, logs=None):
            # only concerned with m['To'] and m['CC'], which are added in
            # _got_recipients later
            return m
        mn.createEmail = fakeCreateEmail

        self.db = fakedb.FakeDBConnector(self)
        self.db.insertTestData([fakedb.SourceStampSet(id=1099),
                                fakedb.Buildset(id=99, sourcestampsetid=1099,
                                                results=SUCCESS,
                                                reason="testReason"),
                                fakedb.BuildRequest(id=11, buildsetid=99,
                                                    buildername='Builder'),
                                fakedb.Build(number=0, brid=11),
                                fakedb.Build(number=1, brid=11),
                                fakedb.Change(changeid=9123),
                                fakedb.Change(changeid=9124),
                                fakedb.ChangeUser(changeid=9123, uid=1),
                                fakedb.ChangeUser(changeid=9124, uid=2),
                                fakedb.User(uid=1, identifier="tdurden"),
                                fakedb.User(uid=2, identifier="user2"),
                                fakedb.UserInfo(uid=1, attr_type='email',
                                            attr_data="tyler@mayhem.net"),
                                fakedb.UserInfo(uid=2, attr_type='email',
                                            attr_data="user2@example.net")
                                ])

        def _getInterestedUsers():
            # 'narrator' in this case is the owner, which tests the lookup
            return ["Big Bob <bob@mayhem.net>", "narrator"]
        build1.getInterestedUsers = _getInterestedUsers
        build2.getInterestedUsers = _getInterestedUsers

        def _getResponsibleUsers():
            return ["Big Bob <bob@mayhem.net>"]
        build1.getResponsibleUsers = _getResponsibleUsers
        build2.getResponsibleUsers = _getResponsibleUsers

        # fake sourcestamp with relevant user bits
        ss1 = Mock(name="sourcestamp")
        fake_change1 = Mock(name="change")
        fake_change1.number = 9123
        ss1.changes = [fake_change1]
        ss1.patch, ss1.addPatch = None, None

        ss2 = Mock(name="sourcestamp")
        fake_change2 = Mock(name="change")
        fake_change2.number = 9124
        ss2.changes = [fake_change2]
        ss2.patch, ss1.addPatch = None, None

        def fakeGetSS(ss):
            return lambda: ss
        build1.getSourceStamp = fakeGetSS(ss1)
        build2.getSourceStamp = fakeGetSS(ss2)

        mn.parent = self
        self.status = mn.master_status = mn.buildMessageDict = Mock()
        mn.master_status.getBuilder = fakeGetBuilder
        mn.buildMessageDict.return_value = {"body": "body", "type": "text"}

        mn.buildMessage(builder.name, [build1, build2], build1.result)
        self.assertEqual(m['To'], "tyler@mayhem.net, user2@example.net")

def create_msgdict():
    unibody = u'Unicode body with non-ascii (\u00E5\u00E4\u00F6).'
    msg_dict = dict(body=unibody, type='plain')
    return msg_dict
