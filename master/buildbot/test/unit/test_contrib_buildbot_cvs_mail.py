import sys
import datetime
import re
import subprocess
import os

from twisted.trial import unittest

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

class TestBuildbotCvsMail(unittest.TestCase):
    buildbot_cvs_mail_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../contrib/buildbot_cvs_mail.py'))

    def assertOutputOk(self, p, stdout, regexList):
        self.failUnlessEqual(p.returncode, 0, "subprocess exited uncleanly")
        lines = stdout.splitlines()
        self.failUnlessEqual(len(lines), len(regexList),
                    "got wrong number of lines of output")

        misses = []
        for line, regex in zip(lines, regexList):
            m = re.search(regex, line)
            if not m:
                misses.append((regex,line))
        self.assertEqual(misses, [], "got non-matching lines")
            
    def test_buildbot_cvs_mail_from_cvs1_11(self):
        # Simulate CVS 1.11 
        p = subprocess.Popen( [ sys.executable, self.buildbot_cvs_mail_path, '--cvsroot=\"ext:example:/cvsroot\"',
                               '--email=buildbot@example.com', '-P', 'test', '-R', 'noreply@example.com', '-t',
                               'test', 'README', '1.1,1.2', 'hello.c', '2.2,2.3'],
                              stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        
        stdoutdata, stderrdata = p.communicate(test)
        #print 'CVS 1.11 stdout: ', stdoutdata

        self.assertOutputOk(p, stdoutdata, golden_1_11_regex )

    def test_buildbot_cvs_mail_from_cvs1_12(self):
        # Simulate CVS 1.12, with --path option
        p = subprocess.Popen( [ sys.executable, self.buildbot_cvs_mail_path, '--cvsroot=\"ext:example.com:/cvsroot\"',
                               '--email=buildbot@example.com', '-P', 'test', '--path', 'test',
                               '-R', 'noreply@example.com', '-t', 
                               'README', '1.1', '1.2', 'hello.c', '2.2', '2.3'], 
                              stdin=subprocess.PIPE, stdout=subprocess.PIPE)

        stdoutdata, stderrdata = p.communicate(test)
        #print 'CVS 1.12 stdout: ', stdoutdata

        self.assertOutputOk(p, stdoutdata, golden_1_12_regex )

    def test_buildbot_cvs_mail_no_args_exits_with_error(self):
        p = subprocess.Popen( [ sys.executable, self.buildbot_cvs_mail_path ], 
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        ret = p.wait()
        self.assert_(ret == 2)
        
    def test_buildbot_cvs_mail_without_email_opt_exits_with_error(self):
        p = subprocess.Popen( [ sys.executable, self.buildbot_cvs_mail_path, '--cvsroot=\"ext:example.com:/cvsroot\"',
                                '-P', 'test', '--path', 'test',
                                '-R', 'noreply@example.com', '-t', 
                                'README', '1.1', '1.2', 'hello.c', '2.2', '2.3'], 
                              stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        ret = p.wait()
        self.assert_(ret == 2)

    def test_buildbot_cvs_mail_without_cvsroot_opt_exits_with_error(self):
        p = subprocess.Popen( [ sys.executable, self.buildbot_cvs_mail_path, '--complete-garbage-opt=gomi',
                                '--cvsroot=\"ext:example.com:/cvsroot\"',
                                '--email=buildbot@example.com','-P', 'test', '--path', 'test',
                                '-R', 'noreply@example.com', '-t', 
                                'README', '1.1', '1.2', 'hello.c', '2.2', '2.3'], 
                              stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        ret = p.wait()
        self.assert_(ret == 2)

    def test_buildbot_cvs_mail_with_unknown_opt_exits_with_error(self):
        p = subprocess.Popen( [ sys.executable, self.buildbot_cvs_mail_path,
                                '--email=buildbot@example.com','-P', 'test', '--path', 'test',
                                '-R', 'noreply@example.com', '-t', 
                                'README', '1.1', '1.2', 'hello.c', '2.2', '2.3'], 
                              stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        ret = p.wait()
        self.assert_(ret == 2)
