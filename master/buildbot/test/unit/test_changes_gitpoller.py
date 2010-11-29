from twisted.trial import unittest
from twisted.internet import defer, utils
from exceptions import Exception
from buildbot.changes import gitpoller
from buildbot.test.util import changesource

class GitOutputHelper:
    """just used to keep shared vars out of the global namespace"""
    desiredOutput = None

# single instance
helper = GitOutputHelper()

# the following methods are used in the monkey-patching, below
def produce_desired_git_output(*args, **kwargs):
    return defer.succeed(helper.desiredOutput)
    
def produce_empty_git_output(*args, **kwargs):
    return defer.succeed('')

def produce_exception_git_output(*args, **kwargs):
    return defer.fail(Exception('fake'))

class GitOutputParsing(unittest.TestCase):
    """Test GitPoller methods for parsing git output"""
    def setUp(self):
        self.poller = gitpoller.GitPoller('git@example.com:foo/baz.git')
        
    def _perform_git_output_test(self, methodToTest,
                                 desiredGoodOutput, desiredGoodResult,
                                 emptyRaisesException=True):
        """
        This method will monkey-patch getProcessOutput to produce different
        scenarios for testing methods which
        """
        dummyRevStr = '12345abcde'

        d = defer.succeed(None)
        def call_empty(_):
            # we should get an Exception with empty output from git
            self.patch(utils, "getProcessOutput", produce_empty_git_output)
            return methodToTest(dummyRevStr)
        d.addCallback(call_empty)
    
        def cb_empty(_):
            if emptyRaisesException:
                self.fail("getProcessOutput should have failed on empty output")
        def eb_empty(f):
            if not emptyRaisesException:
                self.fail("getProcessOutput should NOT have failed on empty output")
        d.addCallbacks(cb_empty, eb_empty)

        # and the method shouldn't supress any exceptions
        def call_exception(_):
            # we should get an Exception with empty output from git
            self.patch(utils, "getProcessOutput", produce_exception_git_output)
            return methodToTest(dummyRevStr)
        d.addCallback(call_exception)
    
        def cb_exception(_):
            self.fail("getProcessOutput should have failed on empty output")
        def eb_exception(f):
            pass
        d.addCallbacks(cb_exception, eb_exception)

        # finally we should get what's expected from good output
        helper.desiredOutput = desiredGoodOutput
        def call_desired(_):
            # we should get an Exception with empty output from git
            self.patch(utils, "getProcessOutput", produce_desired_git_output)
            return methodToTest(dummyRevStr)
        d.addCallback(call_desired)
    
        def cb_desired(r):
            self.assertEquals(r, desiredGoodResult)
        d.addCallback(cb_desired)
        
    def test_get_commit_name(self):
        nameStr = 'Sammy Jankis'
        return self._perform_git_output_test(self.poller._get_commit_name,
                nameStr, nameStr)
        
    def test_get_commit_comments(self):
        commentStr = 'this is a commit message\n\nthat is multiline'
        return self._perform_git_output_test(self.poller._get_commit_comments,
                commentStr, commentStr)
        
    def test_get_commit_files(self):
        filesStr = 'file1\nfile2'
        return self._perform_git_output_test(self.poller._get_commit_files, filesStr, 
                                      filesStr.split(), emptyRaisesException=False)    
        
    def test_get_commit_timestamp(self):
        stampStr = '1273258009'
        return self._perform_git_output_test(self.poller._get_commit_timestamp,
                stampStr, float(stampStr))

    # _get_changes is tested in TestPolling, below

class TestPolling(changesource.ChangeSourceMixin, unittest.TestCase):
    def setUp(self):
        d = self.setUpChangeSource()
        def create_poller(_):
            self.poller = gitpoller.GitPoller('git@example.com:foo/baz.git')
            self.poller.parent = self.changemaster
        d.addCallback(create_poller)
        return d
        
    def tearDown(self):
        return self.tearDownChangeSource()

    def test_poll(self):
        # patch out getProcessOutput and getProcessOutputAndValue for the
        # benefit of the _get_changes method
        def gpo_fetch_and_log(bin, cmd, *args, **kwargs):
            if cmd[0] == 'fetch':
                return defer.succeed('no interesting output')
            if cmd[0] == 'log':
                return defer.succeed('\n'.join([
                    '64a5dc2a4bd4f558b5dd193d47c83c7d7abc9a1a',
                    '4423cdbcbb89c14e50dd5f4152415afd686c5241']))
            assert 0, "bad command"
        self.patch(utils, "getProcessOutput", gpo_fetch_and_log)

        def gpoav(bin, cmd, *args, **kwargs):
            if cmd[0] == 'reset':
                return defer.succeed(('done', '', 0))
            assert 0, "bad command"

        # and patch out the _get_commit_foo methods which were already tested
        # above
        def timestamp(rev):
            self.poller.commitInfo['timestamp'] = 1273258009.0
            return defer.succeed(None)
        self.patch(self.poller, '_get_commit_timestamp', timestamp)
        def name(rev):
            self.poller.commitInfo['name'] = 'by:' + rev[:8]
            return defer.succeed(None)
        self.patch(self.poller, '_get_commit_name', name)
        def files(rev):
            self.poller.commitInfo['files'] = ['/etc/' + rev[:3]]
            return defer.succeed(None)
        self.patch(self.poller, '_get_commit_files', files)
        def comments(rev):
            self.poller.commitInfo['comments'] = 'hello!'
            return defer.succeed(None)
        self.patch(self.poller, '_get_commit_comments', comments)

        # do the poll
        d = self.poller.poll()

        # check the results
        def check(_):
            self.assertEqual(len(self.changes_added), 2)
            self.assertEqual(self.changes_added[0].who, 'by:4423cdbc')
            self.assertEqual(self.changes_added[0].when, 1273258009.0)
            self.assertEqual(self.changes_added[0].comments, 'hello!')
            self.assertEqual(self.changes_added[0].branch, 'master')
            self.assertEqual(self.changes_added[0].files, [ '/etc/442' ])
            self.assertEqual(self.changes_added[1].who, 'by:64a5dc2a')
            self.assertEqual(self.changes_added[1].when, 1273258009.0)
            self.assertEqual(self.changes_added[1].comments, 'hello!')
            self.assertEqual(self.changes_added[1].files, [ '/etc/64a' ])
        d.addCallback(check)

        return d
