from twisted.trial import unittest
from exceptions import Exception
from buildbot.changes import gitpoller

class GitOutputHelper:
    """just used to keep shared vars out of the global namespace"""
    desiredOutput = None

# single instance
helper = GitOutputHelper()

# the following methods are used in place of 
# GitPoller._get_git_output(self, args)
def produce_desired_git_output(args):
    return helper.desiredOutput
    
def produce_empty_git_output(args):
    return ''

def produce_exception_git_output(args):
   raise Exception('fake')

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

        # we should get an Exception with empty output from git
        self.gp._get_git_output = produce_empty_git_output
        
        if emptyRaisesException:
            self.assertRaises(Exception, methodToTest, dummyRevStr)
        else:
            try:
                methodToTest(dummyRevStr)
            except Exception, e:
                self.fail('unexpected exception \'%s\' from empty output' % e)
        
        # and the method shouldn't supress any exceptions
        self.gp._get_git_output = produce_exception_git_output
        self.assertRaises(Exception, methodToTest, dummyRevStr)
        
        # finally we should get what's expected from good output
        helper.desiredOutput = desiredGoodOutput
        self.gp._get_git_output = produce_desired_git_output
        self.assertEquals(methodToTest(dummyRevStr), desiredGoodResult)
        
    def test_get_commit_name(self):
        nameStr = 'Sammy Jankis'
        self._perform_git_output_test(self.gp._get_commit_name, nameStr, nameStr)
        
    def test_get_commit_comments(self):
        commentStr = 'this is a commit message\n\nthat is multiline'
        self._perform_git_output_test(self.gp._get_commit_comments, commentStr, commentStr)
        
    def test_get_commit_files(self):
        filesStr = 'file1\nfile2'
        self._perform_git_output_test(self.gp._get_commit_files, filesStr, 
                                      filesStr.split(), emptyRaisesException=False)    
        
    def test_get_commit_timestamp(self):
        stampStr = '1273258009'
        self._perform_git_output_test(self.gp._get_commit_timestamp, stampStr, float(stampStr))
