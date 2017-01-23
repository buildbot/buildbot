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

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from future.utils import text_type

import os
import re
import sys

from twisted.internet import defer
from twisted.internet import protocol
from twisted.internet import reactor
from twisted.internet import utils
from twisted.python import log
from twisted.trial import unittest

from buildbot.test.util.misc import encodeExecutableAndArgs

test = '''
Update of /cvsroot/test
In directory example:/tmp/cvs-serv21085

Modified Files:
        README hello.c
Log Message:
two files checkin

'''
golden_1_11_regex = [
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

golden_1_12_regex = [
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
    '^$']


class _SubprocessProtocol(protocol.ProcessProtocol):

    def __init__(self, input, deferred):
        if isinstance(input, text_type):
            input = input.encode('utf-8')
        self.input = input
        self.deferred = deferred
        self.output = b''

    def outReceived(self, s):
        self.output += s
    errReceived = outReceived

    def connectionMade(self):
        # push the input and send EOF
        self.transport.write(self.input)
        self.transport.closeStdin()

    def processEnded(self, reason):
        self.deferred.callback((self.output, reason.value.exitCode))


def getProcessOutputAndValueWithInput(executable, args, input):
    "similar to getProcessOutputAndValue, but also allows injection of input on stdin"
    d = defer.Deferred()
    p = _SubprocessProtocol(input, d)

    (executable, args) = encodeExecutableAndArgs(executable, args)
    reactor.spawnProcess(p, executable, (executable,) + tuple(args))
    return d


class TestBuildbotCvsMail(unittest.TestCase):
    buildbot_cvs_mail_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), '../../../contrib/buildbot_cvs_mail.py'))
    if not os.path.exists(buildbot_cvs_mail_path):
        skip = ("'%s' does not exist (normal unless run from git)"
                % buildbot_cvs_mail_path)

    def assertOutputOk(self, result, regexList):
        "assert that the output from getProcessOutputAndValueWithInput matches expectations"
        (output, code) = result
        if isinstance(output, bytes):
            output = output.decode("utf-8")
        try:
            self.assertEqual(code, 0, "subprocess exited uncleanly")
            lines = output.splitlines()
            self.assertEqual(len(lines), len(regexList),
                             "got wrong number of lines of output")

            misses = []
            for line, regex in zip(lines, regexList):
                m = re.search(regex, line)
                if not m:
                    misses.append((regex, line))
            self.assertEqual(misses, [], "got non-matching lines")
        except Exception:
            log.msg("got output:\n" + output)
            raise

    def test_buildbot_cvs_mail_from_cvs1_11(self):
        # Simulate CVS 1.11
        executable = sys.executable
        args = [self.buildbot_cvs_mail_path, '--cvsroot=\"ext:example:/cvsroot\"',
                '--email=buildbot@example.com', '-P', 'test', '-R', 'noreply@example.com', '-t',
                'test', 'README', '1.1,1.2', 'hello.c', '2.2,2.3']
        (executable, args) = encodeExecutableAndArgs(executable, args)
        d = getProcessOutputAndValueWithInput(executable,
                                              args,
                                              input=test)
        d.addCallback(self.assertOutputOk, golden_1_11_regex)
        return d

    def test_buildbot_cvs_mail_from_cvs1_12(self):
        # Simulate CVS 1.12, with --path option
        executable = sys.executable
        args = [self.buildbot_cvs_mail_path, '--cvsroot=\"ext:example.com:/cvsroot\"',
                '--email=buildbot@example.com', '-P', 'test', '--path', 'test',
                '-R', 'noreply@example.com', '-t',
                'README', '1.1', '1.2', 'hello.c', '2.2', '2.3']
        (executable, args) = encodeExecutableAndArgs(executable, args)
        d = getProcessOutputAndValueWithInput(executable,
                                              args,
                                              input=test)
        d.addCallback(self.assertOutputOk, golden_1_12_regex)
        return d

    def test_buildbot_cvs_mail_no_args_exits_with_error(self):
        executable = sys.executable
        args = [self.buildbot_cvs_mail_path]
        (executable, args) = encodeExecutableAndArgs(executable, args)
        d = utils.getProcessOutputAndValue(executable, args)

        def check(result):
            (stdout, stderr, code) = result
            self.assertEqual(code, 2)
        d.addCallback(check)
        return d

    def test_buildbot_cvs_mail_without_email_opt_exits_with_error(self):
        executable = sys.executable
        args = [self.buildbot_cvs_mail_path,
                '--cvsroot=\"ext:example.com:/cvsroot\"',
                '-P', 'test', '--path', 'test',
                '-R', 'noreply@example.com', '-t',
                'README', '1.1', '1.2', 'hello.c', '2.2', '2.3']
        (executable, args) = encodeExecutableAndArgs(executable, args)
        d = utils.getProcessOutputAndValue(executable, args)

        def check(result):
            (stdout, stderr, code) = result
            self.assertEqual(code, 2)
        d.addCallback(check)
        return d

    def test_buildbot_cvs_mail_without_cvsroot_opt_exits_with_error(self):
        executable = sys.executable
        args = [self.buildbot_cvs_mail_path, '--complete-garbage-opt=gomi',
                '--cvsroot=\"ext:example.com:/cvsroot\"',
                '--email=buildbot@example.com', '-P', 'test', '--path',
                'test', '-R', 'noreply@example.com', '-t',
                'README', '1.1', '1.2', 'hello.c', '2.2', '2.3']
        (executable, args) = encodeExecutableAndArgs(executable, args)
        d = utils.getProcessOutputAndValue(executable, args)

        def check(result):
            (stdout, stderr, code) = result
            self.assertEqual(code, 2)
        d.addCallback(check)
        return d

    def test_buildbot_cvs_mail_with_unknown_opt_exits_with_error(self):
        executable = sys.executable
        args = [self.buildbot_cvs_mail_path,
                '--email=buildbot@example.com', '-P', 'test', '--path',
                'test', '-R', 'noreply@example.com', '-t',
                'README', '1.1', '1.2', 'hello.c', '2.2', '2.3']
        (executable, args) = encodeExecutableAndArgs(executable, args)
        d = utils.getProcessOutputAndValue(executable, args)

        def check(result):
            (stdout, stderr, code) = result
            self.assertEqual(code, 2)
        d.addCallback(check)
        return d
