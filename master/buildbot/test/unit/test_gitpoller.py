from twisted.trial import unittest
from twisted.internet import defer, utils
from exceptions import Exception
from buildbot.changes import gitpoller

class GitOutputHelper:
    """just used to keep shared vars out of the global namespace"""
    desiredOutput = None

# single instance
helper = GitOutputHelper()

# the following methods are used in place of 
# GitPoller._get_git_output(self, args)
def produce_desired_git_output(*args, **kwargs):
    return defer.succeed(helper.desiredOutput)
    
def produce_empty_git_output(*args, **kwargs):
    return defer.succeed('')

def produce_exception_git_output(*args, **kwargs):
    return defer.fail(Exception('fake'))

class GitOutputParsing(unittest.TestCase):
    """Test GitPoller methods that rely on GitPoller._get_git_output()"""
    gp = None
    
    def setUp(self):
        self.gp = gitpoller.GitPoller('git@example.com:foo/baz.git')
        
    def _perform_git_output_test(self, methodToTest,
                                 desiredGoodOutput, desiredGoodResult,
                                 emptyRaisesException=True):
        """
        This method will monkey-patch the GitPoller instance's _get_git_output() 
        method to produce different scenarios for testing methods which
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
        return self._perform_git_output_test(self.gp._get_commit_name,
                nameStr, nameStr)
        
    def test_get_commit_comments(self):
        commentStr = 'this is a commit message\n\nthat is multiline'
        return self._perform_git_output_test(self.gp._get_commit_comments,
                commentStr, commentStr)
        
    def test_get_commit_files(self):
        filesStr = 'file1\nfile2'
        return self._perform_git_output_test(self.gp._get_commit_files, filesStr, 
                                      filesStr.split(), emptyRaisesException=False)    
        
    def test_get_commit_timestamp(self):
        stampStr = '1273258009'
        return self._perform_git_output_test(self.gp._get_commit_timestamp,
                stampStr, float(stampStr))
