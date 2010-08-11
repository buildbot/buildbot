import sys
from mock import Mock, patch_object
from buildbot.interfaces import ParameterError
from twisted.trial import unittest

from email import message_from_string
from email.Utils import parseaddr, parsedate_tz, mktime_tz
import datetime
from buildbot.status.builder import SUCCESS, FAILURE
from buildbot.changes.mail import MaildirSource, BuildbotCVSMaildirSource
import re
import shlex, subprocess
import os

test = '''
Update of /cvsroot/test
In directory example:/tmp/cvs-serv21085

Modified Files:
        README hello.c
Log Message:
two files checkin

'''
golden_1_11_regex=[
    '^From:',
    '^To: buildbot@example.com$',
    '^Reply-To: noreply@example.com$',
    '^Subject: cvs update for project test$',
    '^Date:',
    '^X-Mailer: Python buildbot-cvs-mail',
    '^$',
    '^Cvsmode: 1.11$',
    '^Category: None',
    '^CVSROOT: \"ext:example:/cvsroot\"',
    '^Files: test README 1.1,1.2 hello.c 2.2,2.3$',
    '^Project: test$',
    '^$',
    '^Update of /cvsroot/test$',
    '^In directory example:/tmp/cvs-serv21085$',
    '^$',
    '^Modified Files:$',
    'README hello.c$',
    'Log Message:$',
    '^two files checkin',
    '^$',
    '^$']
    
golden_1_12_regex=[
    '^From: ',
    '^To: buildbot@example.com$',
    '^Reply-To: noreply@example.com$',
    '^Subject: cvs update for project test$',
    '^Date: ',
    '^X-Mailer: Python buildbot-cvs-mail',
    '^$',
    '^Cvsmode: 1.12$',
    '^Category: None$',
    '^CVSROOT: \"ext:example.com:/cvsroot\"$',
    '^Files: README 1.1 1.2 hello.c 2.2 2.3$',
    '^Path: test$',
    '^Project: test$',
    '^$',
    '^Update of /cvsroot/test$',
    '^In directory example:/tmp/cvs-serv21085$',
    '^$',
    '^Modified Files:$',
    'README hello.c$',
    '^Log Message:$',
    'two files checkin',
    '^$',
    '^$' ]

def checkOutput( stdout, regexList ):
    misses = 0;
    lineNo = 0
    for line in stdout.splitlines():
        m = re.search(regexList[lineNo], line)
        if not m:
            #print "line %d %s didn't match %s" % (lineNo, line, regexList[lineNo] )
            misses += 1
        lineNo += 1
    return misses
        
class TestBuildbotCvsMail(unittest.TestCase):
    buildbot_cvs_mail_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../contrib/buildbot_cvs_mail.py'))

    def test_buildbot_cvs_mail_from_cvs1_11(self):
        # Simulate CVS 1.11 
        p = subprocess.Popen( [ sys.executable, self.buildbot_cvs_mail_path, '--cvsroot=\"ext:example:/cvsroot\"',
                               '--email=buildbot@example.com', '-P', 'test', '-R', 'noreply@example.com', '-t',
                               'test', 'README', '1.1,1.2', 'hello.c', '2.2,2.3'],
                              stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        stdoutdata, stderrdata = p.communicate(test)
        #print 'CVS 1.11 stdout: ', stdoutdata

        misses = checkOutput( stdoutdata, golden_1_11_regex )
        self.assert_(misses == 0 )

    def test_buildbot_cvs_mail_from_cvs1_12(self):
        # Simulate CVS 1.12, with --path option
        p = subprocess.Popen( [ sys.executable, self.buildbot_cvs_mail_path, '--cvsroot=\"ext:example.com:/cvsroot\"',
                               '--email=buildbot@example.com', '-P', 'test', '--path', 'test',
                               '-R', 'noreply@example.com', '-t', 
                               'README', '1.1', '1.2', 'hello.c', '2.2', '2.3'], 
                              stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        stdoutdata, stderrdata = p.communicate(test)
        #print 'CVS 1.12 stdout: ', stdoutdata

        misses = checkOutput( stdoutdata, golden_1_12_regex )
        self.assert_(misses == 0 )
