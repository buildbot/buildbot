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
from buildbot.interfaces import ParameterError
from twisted.trial import unittest

from buildbot.status.results import SUCCESS, FAILURE
from buildbot.status.mail import MailNotifier
from twisted.internet import defer
from buildbot.test.fake import fakedb

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
        build = Mock()
        msgdict = create_msgdict()
        mn = MailNotifier('from@example.org')
        m = mn.createEmail(msgdict, u'builder-n\u00E5me', u'project-n\u00E5me',
                           SUCCESS, build)
        try:
            m.as_string()
        except UnicodeEncodeError:
            self.fail('Failed to call as_string() on email message.')

    def test_createEmail_message_with_patch_and_log_contains_unicode(self):
        build = Mock()
        msgdict = create_msgdict()
        patch = ['', u'\u00E5\u00E4\u00F6', '']
        logs = [FakeLog(u'Unicode log with non-ascii (\u00E5\u00E4\u00F6).')]
        mn = MailNotifier('from@example.org', addLogs=True)
        m = mn.createEmail(msgdict, u'builder-n\u00E5me',
                           u'project-n\u00E5me', SUCCESS,
                           [build], [patch], logs)
        try:
            m.as_string()
        except UnicodeEncodeError:
            self.fail('Failed to call as_string() on email message.')

    def test_init_enforces_categories_and_builders_are_mutually_exclusive(self):
        self.assertRaises(ParameterError,
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

        build = Mock()

        self.assertEqual(None, mn.buildFinished('dummyBuilder', build, SUCCESS))
        
    def test_buildsetFinished_sends_email(self):
        fakeBuildMessage = Mock()
        mn = MailNotifier('from@example.org', 
                          buildSetSummary=True, 
                          mode="all",
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
        
        build = Mock()
        build.result = FAILURE
        build.finished = True
        build.reason = "testReason"
        build.builder = builder
        build.getBuilder = Mock()
        build.getBuilder.return_value = builder
       
       
        self.db = fakedb.FakeDBConnector(self)
        self.db.insertTestData([fakedb.Buildset(id=99, sourcestampid=127,
                                                results=SUCCESS,
                                                reason="testReason"),
                                fakedb.BuildRequest(id=11, buildsetid=99,
                                                    buildername='Builder'),
                                fakedb.Build(number=0, brid=11, results=SUCCESS)
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


        build = Mock()
        builder = Mock()
        build.getBuilder.return_value = builder
        builder.category = 'slow'

        self.assertEqual(None, mn.buildFinished('dummyBuilder', build, SUCCESS))

    def test_buildFinished_mode_all_always_sends_email(self):
        mock_method = Mock()
        self.patch(MailNotifier, "buildMessage", mock_method)
        mn = MailNotifier('from@example.org', mode="all")

        build = Mock()
        mn.buildFinished('dummyBuilder', build, FAILURE)

        mock_method.assert_called_with('dummyBuilder', [build], FAILURE)

    def test_buildFinished_mode_failing_ignores_successful_build(self):
        mn = MailNotifier('from@example.org', mode="failing")

        build = Mock()

        self.assertEqual(None, mn.buildFinished('dummyBuilder', build, SUCCESS))

    def test_buildFinished_mode_passing_ignores_failed_build(self):
        mn = MailNotifier('from@example.org', mode="passing")

        build = Mock()

        self.assertEqual(None, mn.buildFinished('dummyBuilder', build, FAILURE))

    def test_buildFinished_mode_problem_ignores_successful_build(self):
        mn = MailNotifier('from@example.org', mode="problem")

        build = Mock()

        self.assertEqual(None, mn.buildFinished('dummyBuilder', build, SUCCESS))

    def test_buildFinished_mode_problem_ignores_two_failed_builds_in_sequence(self):
        mn = MailNotifier('from@example.org', mode="problem")

        build = Mock()
        old_build = Mock()
        build.getPreviousBuild.return_value = old_build
        old_build.getResults.return_value = FAILURE

        self.assertEqual(None, mn.buildFinished('dummyBuilder', build, FAILURE))

    def test_buildFinished_mode_change_ignores_first_build(self):
        mn = MailNotifier('from@example.org', mode="change")

        build = Mock()
        build.getPreviousBuild.return_value = None

        self.assertEqual(None, mn.buildFinished('dummyBuilder', build, FAILURE))
        self.assertEqual(None, mn.buildFinished('dummyBuilder', build, SUCCESS))


    def test_buildFinished_mode_change_ignores_same_result_in_sequence(self):
        mn = MailNotifier('from@example.org', mode="change")

        build = Mock()
        old_build = Mock()
        build.getPreviousBuild.return_value = old_build
        old_build.getResults.return_value = FAILURE

        build2 = Mock()
        old_build2 = Mock()
        build2.getPreviousBuild.return_value = old_build2
        old_build2.getResults.return_value = SUCCESS

        self.assertEqual(None, mn.buildFinished('dummyBuilder', build, FAILURE))
        self.assertEqual(None, mn.buildFinished('dummyBuilder', build2, SUCCESS))
    pass

def create_msgdict():
    unibody = u'Unicode body with non-ascii (\u00E5\u00E4\u00F6).'
    msg_dict = dict(body=unibody, type='plain')
    return msg_dict
