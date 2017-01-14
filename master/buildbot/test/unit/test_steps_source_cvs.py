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
from __future__ import print_function

import time

from twisted.internet import error
from twisted.trial import unittest

from buildbot.process import remotetransfer
from buildbot.process.results import FAILURE
from buildbot.process.results import RETRY
from buildbot.process.results import SUCCESS
from buildbot.steps.source import cvs
from buildbot.test.fake.remotecommand import Expect
from buildbot.test.fake.remotecommand import ExpectRemoteRef
from buildbot.test.fake.remotecommand import ExpectShell
from buildbot.test.util import sourcesteps


def uploadString(cvsroot):
    def behavior(command):
        writer = command.args['writer']
        writer.remote_write(cvsroot + "\n")
        writer.remote_close()
    return behavior


class TestCVS(sourcesteps.SourceStepMixin, unittest.TestCase):

    def setUp(self):
        return self.setUpSourceStep()

    def tearDown(self):
        return self.tearDownSourceStep()

    def setupStep(self, step, *args, **kwargs):
        sourcesteps.SourceStepMixin.setupStep(self, step, *args, **kwargs)

        # make parseGotRevision return something consistent, patching the class
        # instead of the object since a new object is constructed by runTest.
        def parseGotRevision(self, res):
            self.updateSourceProperty('got_revision',
                                      '2012-09-09 12:00:39 +0000')
            return res
        self.patch(cvs.CVS, 'parseGotRevision', parseGotRevision)

    def test_parseGotRevision(self):
        def gmtime():
            return time.struct_time((2012, 9, 9, 12, 9, 33, 6, 253, 0))
        self.patch(time, 'gmtime', gmtime)

        step = cvs.CVS(cvsroot="x", cvsmodule="m", mode='full', method='clean')
        props = []

        def updateSourceProperty(prop, name):
            props.append((prop, name))
        step.updateSourceProperty = updateSourceProperty

        self.assertEqual(step.parseGotRevision(10), 10)  # passes res along
        self.assertEqual(props,
                         [('got_revision', '2012-09-09 12:09:33 +0000')])

    def test_cvsEntriesContainStickyDates(self):
        step = cvs.CVS(cvsroot="x", cvsmodule="m", mode='full', method='clean')
        self.assertEqual(step._cvsEntriesContainStickyDates('D'), False)
        self.assertEqual(step._cvsEntriesContainStickyDates(
            '/file/1.1/Fri May 17 23:20:00//TMOZILLA_1_0_0_BRANCH\nD'), False)
        self.assertEqual(step._cvsEntriesContainStickyDates(
            '/file/1.1/Fri May 17 23:20:00//D2013.10.08.11.20.33\nD'), True)
        self.assertEqual(step._cvsEntriesContainStickyDates(
            '/file1/1.1/Fri May 17 23:20:00//\n/file2/1.1.2.3/Fri May 17 23:20:00//D2013.10.08.11.20.33\nD'), True)

    def test_mode_full_clean_and_login(self):
        self.setupStep(
            cvs.CVS(cvsroot=":pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot",
                    cvsmodule="mozilla/browser/", mode='full', method='clean',
                    login="a password"))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['cvs', '--version'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['cvs',
                                 '-d',
                                 ':pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot',
                                 'login'],
                        initialStdin="a password\n")
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('uploadFile', dict(blocksize=32768, maxsize=None,
                                      workersrc='Root', workdir='wkdir/CVS',
                                      writer=ExpectRemoteRef(remotetransfer.StringFileWriter)))
            +
            Expect.behavior(
                uploadString(':pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot'))
            + 0,
            Expect('uploadFile', dict(blocksize=32768, maxsize=None,
                                      workersrc='Repository', workdir='wkdir/CVS',
                                      writer=ExpectRemoteRef(remotetransfer.StringFileWriter)))
            + Expect.behavior(uploadString('mozilla/browser/'))
            + 0,
            Expect('uploadFile', dict(blocksize=32768, maxsize=None,
                                      workersrc='Entries', workdir='wkdir/CVS',
                                      writer=ExpectRemoteRef(remotetransfer.StringFileWriter)))
            +
            Expect.behavior(uploadString('/file/1.1/Fri May 17 23:20:00//\nD'))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['cvsdiscard'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['cvs', '-z3', 'update', '-dP'])
            + 0,
        )

        self.expectOutcome(result=SUCCESS, state_string="update")
        self.expectProperty('got_revision', '2012-09-09 12:00:39 +0000', 'CVS')
        return self.runStep()

    def test_mode_full_clean_and_login_worker_2_16(self):
        self.setupStep(
            cvs.CVS(cvsroot=":pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot",
                    cvsmodule="mozilla/browser/", mode='full', method='clean',
                    login="a password"),
            worker_version={'*': '2.16'})

        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['cvs', '--version'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['cvs',
                                 '-d',
                                 ':pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot',
                                 'login'],
                        initialStdin="a password\n")
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('uploadFile', dict(blocksize=32768, maxsize=None,
                                      slavesrc='Root', workdir='wkdir/CVS',
                                      writer=ExpectRemoteRef(remotetransfer.StringFileWriter)))
            +
            Expect.behavior(
                uploadString(':pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot'))
            + 0,
            Expect('uploadFile', dict(blocksize=32768, maxsize=None,
                                      slavesrc='Repository', workdir='wkdir/CVS',
                                      writer=ExpectRemoteRef(remotetransfer.StringFileWriter)))
            + Expect.behavior(uploadString('mozilla/browser/'))
            + 0,
            Expect('uploadFile', dict(blocksize=32768, maxsize=None,
                                      slavesrc='Entries', workdir='wkdir/CVS',
                                      writer=ExpectRemoteRef(remotetransfer.StringFileWriter)))
            +
            Expect.behavior(uploadString('/file/1.1/Fri May 17 23:20:00//\nD'))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['cvsdiscard'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['cvs', '-z3', 'update', '-dP'])
            + 0,
        )

        self.expectOutcome(result=SUCCESS, state_string="update")
        self.expectProperty('got_revision', '2012-09-09 12:00:39 +0000', 'CVS')
        return self.runStep()

    def test_mode_full_clean_patch(self):
        self.setupStep(
            cvs.CVS(cvsroot=":pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot",
                    cvsmodule="mozilla/browser/", mode='full', method='clean'),
            patch=(1, 'patch'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['cvs', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['cvsdiscard'])
            + 0,
            Expect('uploadFile', dict(blocksize=32768, maxsize=None,
                                      workersrc='Root', workdir='wkdir/CVS',
                                      writer=ExpectRemoteRef(remotetransfer.StringFileWriter)))
            +
            Expect.behavior(
                uploadString(':pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot'))
            + 0,
            Expect('uploadFile', dict(blocksize=32768, maxsize=None,
                                      workersrc='Repository', workdir='wkdir/CVS',
                                      writer=ExpectRemoteRef(remotetransfer.StringFileWriter)))
            + Expect.behavior(uploadString('mozilla/browser/'))
            + 0,
            Expect('uploadFile', dict(blocksize=32768, maxsize=None,
                                      workersrc='Entries', workdir='wkdir/CVS',
                                      writer=ExpectRemoteRef(remotetransfer.StringFileWriter)))
            +
            Expect.behavior(uploadString('/file/1.1/Fri May 17 23:20:00//\nD'))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['cvsdiscard'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['cvs', '-z3', 'update', '-dP'])
            + 0,
            Expect('downloadFile', dict(blocksize=16384, maxsize=None,
                                        reader=ExpectRemoteRef(
                                            remotetransfer.StringFileReader),
                                        workerdest='.buildbot-diff', workdir='wkdir',
                                        mode=None))
            + 0,
            Expect('downloadFile', dict(blocksize=16384, maxsize=None,
                                        reader=ExpectRemoteRef(
                                            remotetransfer.StringFileReader),
                                        workerdest='.buildbot-patched', workdir='wkdir',
                                        mode=None))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['patch', '-p1', '--remove-empty-files',
                                 '--force', '--forward', '-i', '.buildbot-diff'])
            + 0,
            Expect('rmdir', dict(dir='wkdir/.buildbot-diff',
                                 logEnviron=True))
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty('got_revision', '2012-09-09 12:00:39 +0000', 'CVS')
        return self.runStep()

    def test_mode_full_clean_patch_worker_2_16(self):
        self.setupStep(
            cvs.CVS(cvsroot=":pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot",
                    cvsmodule="mozilla/browser/", mode='full', method='clean'),
            patch=(1, 'patch'),
            worker_version={'*': '2.16'})
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['cvs', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['cvsdiscard'])
            + 0,
            Expect('uploadFile', dict(blocksize=32768, maxsize=None,
                                      slavesrc='Root', workdir='wkdir/CVS',
                                      writer=ExpectRemoteRef(remotetransfer.StringFileWriter)))
            +
            Expect.behavior(
                uploadString(':pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot'))
            + 0,
            Expect('uploadFile', dict(blocksize=32768, maxsize=None,
                                      slavesrc='Repository', workdir='wkdir/CVS',
                                      writer=ExpectRemoteRef(remotetransfer.StringFileWriter)))
            + Expect.behavior(uploadString('mozilla/browser/'))
            + 0,
            Expect('uploadFile', dict(blocksize=32768, maxsize=None,
                                      slavesrc='Entries', workdir='wkdir/CVS',
                                      writer=ExpectRemoteRef(remotetransfer.StringFileWriter)))
            +
            Expect.behavior(uploadString('/file/1.1/Fri May 17 23:20:00//\nD'))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['cvsdiscard'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['cvs', '-z3', 'update', '-dP'])
            + 0,
            Expect('downloadFile', dict(blocksize=16384, maxsize=None,
                                        reader=ExpectRemoteRef(
                                            remotetransfer.StringFileReader),
                                        slavedest='.buildbot-diff', workdir='wkdir',
                                        mode=None))
            + 0,
            Expect('downloadFile', dict(blocksize=16384, maxsize=None,
                                        reader=ExpectRemoteRef(
                                            remotetransfer.StringFileReader),
                                        slavedest='.buildbot-patched', workdir='wkdir',
                                        mode=None))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['patch', '-p1', '--remove-empty-files',
                                 '--force', '--forward', '-i', '.buildbot-diff'])
            + 0,
            Expect('rmdir', dict(dir='wkdir/.buildbot-diff',
                                 logEnviron=True))
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty('got_revision', '2012-09-09 12:00:39 +0000', 'CVS')
        return self.runStep()

    def test_mode_full_clean_timeout(self):
        self.setupStep(
            cvs.CVS(cvsroot=":pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot",
                    cvsmodule="mozilla/browser/", mode='full', method='clean',
                    timeout=1))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        timeout=1,
                        command=['cvs', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('uploadFile', dict(blocksize=32768, maxsize=None,
                                      workersrc='Root', workdir='wkdir/CVS',
                                      writer=ExpectRemoteRef(remotetransfer.StringFileWriter)))
            +
            Expect.behavior(
                uploadString(':pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot'))
            + 0,
            Expect('uploadFile', dict(blocksize=32768, maxsize=None,
                                      workersrc='Repository', workdir='wkdir/CVS',
                                      writer=ExpectRemoteRef(remotetransfer.StringFileWriter)))
            + Expect.behavior(uploadString('mozilla/browser/'))
            + 0,
            Expect('uploadFile', dict(blocksize=32768, maxsize=None,
                                      workersrc='Entries', workdir='wkdir/CVS',
                                      writer=ExpectRemoteRef(remotetransfer.StringFileWriter)))
            +
            Expect.behavior(uploadString('/file/1.1/Fri May 17 23:20:00//\nD'))
            + 0,
            ExpectShell(workdir='wkdir',
                        timeout=1,
                        command=['cvsdiscard'])
            + 0,
            ExpectShell(workdir='wkdir',
                        timeout=1,
                        command=['cvs', '-z3', 'update', '-dP'])
            + 0,
        )

        self.expectOutcome(result=SUCCESS)
        self.expectProperty('got_revision', '2012-09-09 12:00:39 +0000', 'CVS')
        return self.runStep()

    def test_mode_full_clean_branch(self):
        self.setupStep(
            cvs.CVS(cvsroot=":pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot",
                    cvsmodule="mozilla/browser/", mode='full', method='clean',
                    branch='branch'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['cvs', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('uploadFile', dict(blocksize=32768, maxsize=None,
                                      workersrc='Root', workdir='wkdir/CVS',
                                      writer=ExpectRemoteRef(remotetransfer.StringFileWriter)))
            +
            Expect.behavior(
                uploadString(':pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot'))
            + 0,
            Expect('uploadFile', dict(blocksize=32768, maxsize=None,
                                      workersrc='Repository', workdir='wkdir/CVS',
                                      writer=ExpectRemoteRef(remotetransfer.StringFileWriter)))
            + Expect.behavior(uploadString('mozilla/browser/'))
            + 0,
            Expect('uploadFile', dict(blocksize=32768, maxsize=None,
                                      workersrc='Entries', workdir='wkdir/CVS',
                                      writer=ExpectRemoteRef(remotetransfer.StringFileWriter)))
            +
            Expect.behavior(uploadString('/file/1.1/Fri May 17 23:20:00//\nD'))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['cvsdiscard'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['cvs', '-z3', 'update', '-dP', '-r', 'branch'])
            + 0,
        )

        self.expectOutcome(result=SUCCESS)
        self.expectProperty('got_revision', '2012-09-09 12:00:39 +0000', 'CVS')
        return self.runStep()

    def test_mode_full_clean_branch_sourcestamp(self):
        self.setupStep(
            cvs.CVS(cvsroot=":pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot",
                    cvsmodule="mozilla/browser/", mode='full', method='clean'),
            args={'branch': 'my_branch'})
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['cvs', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('uploadFile', dict(blocksize=32768, maxsize=None,
                                      workersrc='Root', workdir='wkdir/CVS',
                                      writer=ExpectRemoteRef(remotetransfer.StringFileWriter)))
            +
            Expect.behavior(
                uploadString(':pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot'))
            + 0,
            Expect('uploadFile', dict(blocksize=32768, maxsize=None,
                                      workersrc='Repository', workdir='wkdir/CVS',
                                      writer=ExpectRemoteRef(remotetransfer.StringFileWriter)))
            + Expect.behavior(uploadString('mozilla/browser/'))
            + 0,
            Expect('uploadFile', dict(blocksize=32768, maxsize=None,
                                      workersrc='Entries', workdir='wkdir/CVS',
                                      writer=ExpectRemoteRef(remotetransfer.StringFileWriter)))
            +
            Expect.behavior(uploadString('/file/1.1/Fri May 17 23:20:00//\nD'))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['cvsdiscard'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['cvs', '-z3', 'update', '-dP', '-r', 'my_branch'])
            + 0,
        )

        self.expectOutcome(result=SUCCESS)
        self.expectProperty('got_revision', '2012-09-09 12:00:39 +0000', 'CVS')
        return self.runStep()

    def test_mode_full_fresh(self):
        self.setupStep(
            cvs.CVS(cvsroot=":pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot",
                    cvsmodule="mozilla/browser/", mode='full', method='fresh'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['cvs', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('uploadFile', dict(blocksize=32768, maxsize=None,
                                      workersrc='Root', workdir='wkdir/CVS',
                                      writer=ExpectRemoteRef(remotetransfer.StringFileWriter)))
            +
            Expect.behavior(
                uploadString(':pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot'))
            + 0,
            Expect('uploadFile', dict(blocksize=32768, maxsize=None,
                                      workersrc='Repository', workdir='wkdir/CVS',
                                      writer=ExpectRemoteRef(remotetransfer.StringFileWriter)))
            + Expect.behavior(uploadString('mozilla/browser/'))
            + 0,
            Expect('uploadFile', dict(blocksize=32768, maxsize=None,
                                      workersrc='Entries', workdir='wkdir/CVS',
                                      writer=ExpectRemoteRef(remotetransfer.StringFileWriter)))
            +
            Expect.behavior(uploadString('/file/1.1/Fri May 17 23:20:00//\nD'))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['cvsdiscard', '--ignore'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['cvs', '-z3', 'update', '-dP'])
            + 0,
        )

        self.expectOutcome(result=SUCCESS)
        self.expectProperty('got_revision', '2012-09-09 12:00:39 +0000', 'CVS')
        return self.runStep()

    def test_mode_full_clobber(self):
        step = cvs.CVS(cvsroot=":pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot",
                       cvsmodule="mozilla/browser/", mode='full', method='clobber')
        self.setupStep(step)
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['cvs', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('rmdir', dict(dir='wkdir',
                                 logEnviron=True,
                                 timeout=step.timeout))
            + 0,
            ExpectShell(workdir='',
                        command=['cvs',
                                 '-d',
                                 ':pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot',
                                 '-z3', 'checkout', '-d', 'wkdir', 'mozilla/browser/'])
            + 0,
        )

        self.expectOutcome(result=SUCCESS)
        self.expectProperty('got_revision', '2012-09-09 12:00:39 +0000', 'CVS')
        return self.runStep()

    def test_mode_full_clobber_retry(self):
        step = cvs.CVS(cvsroot=":pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot",
                       cvsmodule="mozilla/browser/", mode='full', method='clobber',
                       retry=(0, 2))
        self.setupStep(step)
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['cvs', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('rmdir', dict(dir='wkdir',
                                 logEnviron=True,
                                 timeout=step.timeout))
            + 0,
            ExpectShell(workdir='',
                        command=['cvs',
                                 '-d',
                                 ':pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot',
                                 '-z3', 'checkout', '-d', 'wkdir', 'mozilla/browser/'])
            + 1,
            Expect('rmdir', dict(dir='wkdir',
                                 logEnviron=True,
                                 timeout=step.timeout))
            + 0,
            ExpectShell(workdir='',
                        command=['cvs',
                                 '-d',
                                 ':pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot',
                                 '-z3', 'checkout', '-d', 'wkdir', 'mozilla/browser/'])
            + 1,
            Expect('rmdir', dict(dir='wkdir',
                                 logEnviron=True,
                                 timeout=step.timeout))
            + 0,
            ExpectShell(workdir='',
                        command=['cvs',
                                 '-d',
                                 ':pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot',
                                 '-z3', 'checkout', '-d', 'wkdir', 'mozilla/browser/'])
            + 0,
        )

        self.expectOutcome(result=SUCCESS)
        self.expectProperty('got_revision', '2012-09-09 12:00:39 +0000', 'CVS')
        return self.runStep()

    def test_mode_full_copy(self):
        step = cvs.CVS(cvsroot=":pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot",
                       cvsmodule="mozilla/browser/", mode='full', method='copy')
        self.setupStep(step)
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['cvs', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('rmdir', dict(dir='wkdir',
                                 logEnviron=True,
                                 timeout=step.timeout))
            + 0,
            Expect('uploadFile', dict(blocksize=32768, maxsize=None,
                                      workersrc='Root', workdir='source/CVS',
                                      writer=ExpectRemoteRef(remotetransfer.StringFileWriter)))
            +
            Expect.behavior(
                uploadString(':pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot'))
            + 0,
            Expect('uploadFile', dict(blocksize=32768, maxsize=None,
                                      workersrc='Repository', workdir='source/CVS',
                                      writer=ExpectRemoteRef(remotetransfer.StringFileWriter)))
            + Expect.behavior(uploadString('mozilla/browser/'))
            + 0,
            Expect('uploadFile', dict(blocksize=32768, maxsize=None,
                                      workersrc='Entries', workdir='source/CVS',
                                      writer=ExpectRemoteRef(remotetransfer.StringFileWriter)))
            +
            Expect.behavior(uploadString('/file/1.1/Fri May 17 23:20:00//\nD'))
            + 0,
            ExpectShell(workdir='source',
                        command=['cvs', '-z3', 'update', '-dP'])
            + 0,
            Expect('cpdir', {'fromdir': 'source', 'todir': 'wkdir',
                             'logEnviron': True, 'timeout': step.timeout})
            + 0,
        )

        self.expectOutcome(result=SUCCESS)
        self.expectProperty('got_revision', '2012-09-09 12:00:39 +0000', 'CVS')
        return self.runStep()

    def test_mode_full_copy_wrong_repo(self):
        step = cvs.CVS(cvsroot=":pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot",
                       cvsmodule="mozilla/browser/", mode='full', method='copy')
        self.setupStep(step)
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['cvs', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('rmdir', dict(dir='wkdir',
                                 logEnviron=True,
                                 timeout=step.timeout))
            + 0,
            Expect('uploadFile', dict(blocksize=32768, maxsize=None,
                                      workersrc='Root', workdir='source/CVS',
                                      writer=ExpectRemoteRef(remotetransfer.StringFileWriter)))
            + Expect.behavior(uploadString('the-end-of-the-universe'))
            + 0,
            Expect('rmdir', dict(dir='source',
                                 logEnviron=True,
                                 timeout=step.timeout))
            + 0,
            ExpectShell(workdir='',
                        command=['cvs',
                                 '-d',
                                 ':pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot',
                                 '-z3', 'checkout', '-d', 'source', 'mozilla/browser/'])
            + 0,
            Expect('cpdir', {'fromdir': 'source', 'todir': 'wkdir',
                             'logEnviron': True, 'timeout': step.timeout})
            + 0,
        )

        self.expectOutcome(result=SUCCESS)
        self.expectProperty('got_revision', '2012-09-09 12:00:39 +0000', 'CVS')
        return self.runStep()

    def test_mode_incremental(self):
        self.setupStep(
            cvs.CVS(cvsroot=":pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot",
                    cvsmodule="mozilla/browser/", mode='incremental'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['cvs', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('uploadFile', dict(blocksize=32768, maxsize=None,
                                      workersrc='Root', workdir='wkdir/CVS',
                                      writer=ExpectRemoteRef(remotetransfer.StringFileWriter)))
            +
            Expect.behavior(
                uploadString(':pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot'))
            + 0,
            Expect('uploadFile', dict(blocksize=32768, maxsize=None,
                                      workersrc='Repository', workdir='wkdir/CVS',
                                      writer=ExpectRemoteRef(remotetransfer.StringFileWriter)))
            + Expect.behavior(uploadString('mozilla/browser/'))
            + 0,
            Expect('uploadFile', dict(blocksize=32768, maxsize=None,
                                      workersrc='Entries', workdir='wkdir/CVS',
                                      writer=ExpectRemoteRef(remotetransfer.StringFileWriter)))
            +
            Expect.behavior(uploadString('/file/1.1/Fri May 17 23:20:00//\nD'))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['cvs', '-z3', 'update', '-dP'])
            + 0,
        )

        self.expectOutcome(result=SUCCESS)
        self.expectProperty('got_revision', '2012-09-09 12:00:39 +0000', 'CVS')
        return self.runStep()

    def test_mode_incremental_sticky_date(self):
        step = cvs.CVS(cvsroot=":pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot",
                       cvsmodule="mozilla/browser/", mode='incremental')
        self.setupStep(step)
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['cvs', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('uploadFile', dict(blocksize=32768, maxsize=None,
                                      workersrc='Root', workdir='wkdir/CVS',
                                      writer=ExpectRemoteRef(remotetransfer.StringFileWriter)))
            +
            Expect.behavior(
                uploadString(':pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot'))
            + 0,
            Expect('uploadFile', dict(blocksize=32768, maxsize=None,
                                      workersrc='Repository', workdir='wkdir/CVS',
                                      writer=ExpectRemoteRef(remotetransfer.StringFileWriter)))
            + Expect.behavior(uploadString('mozilla/browser/'))
            + 0,
            Expect('uploadFile', dict(blocksize=32768, maxsize=None,
                                      workersrc='Entries', workdir='wkdir/CVS',
                                      writer=ExpectRemoteRef(remotetransfer.StringFileWriter)))
            +
            Expect.behavior(
                uploadString('/file/1.1/Fri May 17 23:20:00//D2013.10.08.11.20.33\nD'))
            + 0,
            Expect('rmdir', dict(dir='wkdir',
                                 logEnviron=True,
                                 timeout=step.timeout))
            + 0,
            ExpectShell(workdir='',
                        command=['cvs',
                                 '-d',
                                 ':pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot',
                                 '-z3', 'checkout', '-d', 'wkdir', 'mozilla/browser/'])
            + 0,
        )

        self.expectOutcome(result=SUCCESS)
        self.expectProperty('got_revision', '2012-09-09 12:00:39 +0000', 'CVS')
        return self.runStep()

    def test_mode_incremental_password_windows(self):
        self.setupStep(
            cvs.CVS(cvsroot=":pserver:dustin:secrets@cvs-mirror.mozilla.org:/cvsroot",
                    cvsmodule="mozilla/browser/", mode='incremental'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['cvs', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('uploadFile', dict(blocksize=32768, maxsize=None,
                                      workersrc='Root', workdir='wkdir/CVS',
                                      writer=ExpectRemoteRef(remotetransfer.StringFileWriter)))
            # on Windows, this file does not contain the password, per
            # http://trac.buildbot.net/ticket/2355
            + Expect.behavior(
                uploadString(':pserver:dustin@cvs-mirror.mozilla.org:/cvsroot'))
            + 0,
            Expect('uploadFile', dict(blocksize=32768, maxsize=None,
                                      workersrc='Repository', workdir='wkdir/CVS',
                                      writer=ExpectRemoteRef(remotetransfer.StringFileWriter)))
            + Expect.behavior(uploadString('mozilla/browser/'))
            + 0,
            Expect('uploadFile', dict(blocksize=32768, maxsize=None,
                                      workersrc='Entries', workdir='wkdir/CVS',
                                      writer=ExpectRemoteRef(remotetransfer.StringFileWriter)))
            + Expect.behavior(uploadString('/file/1.1/Fri May 17 23:20:00//\nD'))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['cvs', '-z3', 'update', '-dP'])
            + 0,
        )

        self.expectOutcome(result=SUCCESS)
        return self.runStep()

    def test_mode_incremental_branch(self):
        self.setupStep(
            cvs.CVS(cvsroot=":pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot",
                    cvsmodule="mozilla/browser/", mode='incremental',
                    branch='my_branch'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['cvs', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('uploadFile', dict(blocksize=32768, maxsize=None,
                                      workersrc='Root', workdir='wkdir/CVS',
                                      writer=ExpectRemoteRef(remotetransfer.StringFileWriter)))
            +
            Expect.behavior(
                uploadString(':pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot'))
            + 0,
            Expect('uploadFile', dict(blocksize=32768, maxsize=None,
                                      workersrc='Repository', workdir='wkdir/CVS',
                                      writer=ExpectRemoteRef(remotetransfer.StringFileWriter)))
            + Expect.behavior(uploadString('mozilla/browser/'))
            + 0,
            Expect('uploadFile', dict(blocksize=32768, maxsize=None,
                                      workersrc='Entries', workdir='wkdir/CVS',
                                      writer=ExpectRemoteRef(remotetransfer.StringFileWriter)))
            +
            Expect.behavior(uploadString('/file/1.1/Fri May 17 23:20:00//\nD'))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['cvs', '-z3', 'update', '-dP', '-r', 'my_branch'])
            + 0,
        )

        self.expectOutcome(result=SUCCESS)
        self.expectProperty('got_revision', '2012-09-09 12:00:39 +0000', 'CVS')
        return self.runStep()

    def test_mode_incremental_special_case(self):
        self.setupStep(
            cvs.CVS(cvsroot=":pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot",
                    cvsmodule="mozilla/browser/", mode='incremental',
                    branch='HEAD'),
            args=dict(revision='2012-08-16 16:05:16 +0000'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['cvs', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('uploadFile', dict(blocksize=32768, maxsize=None,
                                      workersrc='Root', workdir='wkdir/CVS',
                                      writer=ExpectRemoteRef(remotetransfer.StringFileWriter)))
            +
            Expect.behavior(
                uploadString(':pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot'))
            + 0,
            Expect('uploadFile', dict(blocksize=32768, maxsize=None,
                                      workersrc='Repository', workdir='wkdir/CVS',
                                      writer=ExpectRemoteRef(remotetransfer.StringFileWriter)))
            + Expect.behavior(uploadString('mozilla/browser/'))
            + 0,
            Expect('uploadFile', dict(blocksize=32768, maxsize=None,
                                      workersrc='Entries', workdir='wkdir/CVS',
                                      writer=ExpectRemoteRef(remotetransfer.StringFileWriter)))
            +
            Expect.behavior(uploadString('/file/1.1/Fri May 17 23:20:00//\nD'))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['cvs', '-z3', 'update', '-dP',
                                 # note, no -r HEAD here - that's the special
                                 # case
                                 '-D', '2012-08-16 16:05:16 +0000'])
            + 0,
        )

        self.expectOutcome(result=SUCCESS)
        return self.runStep()

    def test_mode_incremental_branch_sourcestamp(self):
        self.setupStep(
            cvs.CVS(cvsroot=":pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot",
                    cvsmodule="mozilla/browser/", mode='incremental'),
            args={'branch': 'my_branch'})
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['cvs', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('uploadFile', dict(blocksize=32768, maxsize=None,
                                      workersrc='Root', workdir='wkdir/CVS',
                                      writer=ExpectRemoteRef(remotetransfer.StringFileWriter)))
            +
            Expect.behavior(
                uploadString(':pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot'))
            + 0,
            Expect('uploadFile', dict(blocksize=32768, maxsize=None,
                                      workersrc='Repository', workdir='wkdir/CVS',
                                      writer=ExpectRemoteRef(remotetransfer.StringFileWriter)))
            + Expect.behavior(uploadString('mozilla/browser/'))
            + 0,
            Expect('uploadFile', dict(blocksize=32768, maxsize=None,
                                      workersrc='Entries', workdir='wkdir/CVS',
                                      writer=ExpectRemoteRef(remotetransfer.StringFileWriter)))
            +
            Expect.behavior(uploadString('/file/1.1/Fri May 17 23:20:00//\nD'))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['cvs', '-z3', 'update', '-dP', '-r', 'my_branch'])
            + 0,
        )

        self.expectOutcome(result=SUCCESS)
        self.expectProperty('got_revision', '2012-09-09 12:00:39 +0000', 'CVS')
        return self.runStep()

    def test_mode_incremental_not_loggedin(self):
        self.setupStep(
            cvs.CVS(cvsroot=":pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot",
                    cvsmodule="mozilla/browser/", mode='incremental'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['cvs', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('uploadFile', dict(blocksize=32768, maxsize=None,
                                      workersrc='Root', workdir='wkdir/CVS',
                                      writer=ExpectRemoteRef(remotetransfer.StringFileWriter)))
            +
            Expect.behavior(
                uploadString(':pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot'))
            + 0,
            Expect('uploadFile', dict(blocksize=32768, maxsize=None,
                                      workersrc='Repository', workdir='wkdir/CVS',
                                      writer=ExpectRemoteRef(remotetransfer.StringFileWriter)))
            + Expect.behavior(uploadString('mozilla/browser/'))
            + 0,
            Expect('uploadFile', dict(blocksize=32768, maxsize=None,
                                      workersrc='Entries', workdir='wkdir/CVS',
                                      writer=ExpectRemoteRef(remotetransfer.StringFileWriter)))
            +
            Expect.behavior(uploadString('/file/1.1/Fri May 17 23:20:00//\nD'))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['cvs', '-z3', 'update', '-dP'])
            + 0,
        )

        self.expectOutcome(result=SUCCESS)
        self.expectProperty('got_revision', '2012-09-09 12:00:39 +0000', 'CVS')
        return self.runStep()

    def test_mode_incremental_no_existing_repo(self):
        step = cvs.CVS(cvsroot=":pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot",
                       cvsmodule="mozilla/browser/", mode='incremental')
        self.setupStep(step)
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['cvs', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('uploadFile', dict(blocksize=32768, maxsize=None,
                                      workersrc='Root', workdir='wkdir/CVS',
                                      writer=ExpectRemoteRef(remotetransfer.StringFileWriter)))
            + 1,
            Expect('rmdir', dict(dir='wkdir',
                                 logEnviron=True,
                                 timeout=step.timeout))
            + 0,
            ExpectShell(workdir='',
                        command=['cvs',
                                 '-d',
                                 ':pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot',
                                 '-z3', 'checkout', '-d', 'wkdir', 'mozilla/browser/'])
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty('got_revision', '2012-09-09 12:00:39 +0000', 'CVS')
        return self.runStep()

    def test_mode_incremental_retry(self):
        step = cvs.CVS(cvsroot=":pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot",
                       cvsmodule="mozilla/browser/", mode='incremental',
                       retry=(0, 1))
        self.setupStep(step)
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['cvs', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('uploadFile', dict(blocksize=32768, maxsize=None,
                                      workersrc='Root', workdir='wkdir/CVS',
                                      writer=ExpectRemoteRef(remotetransfer.StringFileWriter)))
            + 1,
            Expect('rmdir', dict(dir='wkdir',
                                 logEnviron=True,
                                 timeout=step.timeout))
            + 0,
            ExpectShell(workdir='',
                        command=['cvs',
                                 '-d',
                                 ':pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot',
                                 '-z3', 'checkout', '-d', 'wkdir', 'mozilla/browser/'])
            + 1,
            Expect('rmdir', dict(dir='wkdir',
                                 logEnviron=True,
                                 timeout=step.timeout))
            + 0,
            ExpectShell(workdir='',
                        command=['cvs',
                                 '-d',
                                 ':pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot',
                                 '-z3', 'checkout', '-d', 'wkdir', 'mozilla/browser/'])
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty('got_revision', '2012-09-09 12:00:39 +0000', 'CVS')
        return self.runStep()

    def test_mode_incremental_wrong_repo(self):
        step = cvs.CVS(cvsroot=":pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot",
                       cvsmodule="mozilla/browser/", mode='incremental')
        self.setupStep(step)
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['cvs', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('uploadFile', dict(blocksize=32768, maxsize=None,
                                      workersrc='Root', workdir='wkdir/CVS',
                                      writer=ExpectRemoteRef(remotetransfer.StringFileWriter)))
            + Expect.behavior(uploadString('the-end-of-the-universe'))
            + 0,
            Expect('rmdir', dict(dir='wkdir',
                                 logEnviron=True,
                                 timeout=step.timeout))
            + 0,
            ExpectShell(workdir='',
                        command=['cvs',
                                 '-d',
                                 ':pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot',
                                 '-z3', 'checkout', '-d', 'wkdir', 'mozilla/browser/'])
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty('got_revision', '2012-09-09 12:00:39 +0000', 'CVS')
        return self.runStep()

    def test_mode_incremental_wrong_module(self):
        step = cvs.CVS(cvsroot=":pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot",
                       cvsmodule="mozilla/browser/", mode='incremental')
        self.setupStep(step)
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['cvs', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('uploadFile', dict(blocksize=32768, maxsize=None,
                                      workersrc='Root', workdir='wkdir/CVS',
                                      writer=ExpectRemoteRef(remotetransfer.StringFileWriter)))
            +
            Expect.behavior(
                uploadString(':pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot'))
            + 0,
            Expect('uploadFile', dict(blocksize=32768, maxsize=None,
                                      workersrc='Repository', workdir='wkdir/CVS',
                                      writer=ExpectRemoteRef(remotetransfer.StringFileWriter)))
            + Expect.behavior(uploadString('the-end-of-the-universe'))
            + 0,
            Expect('rmdir', dict(dir='wkdir',
                                 logEnviron=True,
                                 timeout=step.timeout))
            + 0,
            ExpectShell(workdir='',
                        command=['cvs',
                                 '-d',
                                 ':pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot',
                                 '-z3', 'checkout', '-d', 'wkdir', 'mozilla/browser/'])
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty('got_revision', '2012-09-09 12:00:39 +0000', 'CVS')
        return self.runStep()

    def test_mode_full_clean_no_existing_repo(self):
        self.setupStep(
            cvs.CVS(cvsroot=":pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot",
                    cvsmodule="mozilla/browser/", mode='full', method='clean'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['cvs', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('uploadFile', dict(blocksize=32768, maxsize=None,
                                      workersrc='Root', workdir='wkdir/CVS',
                                      writer=ExpectRemoteRef(remotetransfer.StringFileWriter)))
            + 1,
            ExpectShell(workdir='',
                        command=['cvs',
                                 '-d',
                                 ':pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot',
                                 '-z3', 'checkout', '-d', 'wkdir', 'mozilla/browser/'])
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty('got_revision', '2012-09-09 12:00:39 +0000', 'CVS')
        return self.runStep()

    def test_mode_full_clean_wrong_repo(self):
        self.setupStep(
            cvs.CVS(cvsroot=":pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot",
                    cvsmodule="mozilla/browser/", mode='full', method='clean'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['cvs', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('uploadFile', dict(blocksize=32768, maxsize=None,
                                      workersrc='Root', workdir='wkdir/CVS',
                                      writer=ExpectRemoteRef(remotetransfer.StringFileWriter)))
            + Expect.behavior(uploadString('the-end-of-the-universe'))
            + 0,
            ExpectShell(workdir='',
                        command=['cvs',
                                 '-d',
                                 ':pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot',
                                 '-z3', 'checkout', '-d', 'wkdir', 'mozilla/browser/'])
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty('got_revision', '2012-09-09 12:00:39 +0000', 'CVS')
        return self.runStep()

    def test_mode_full_no_method(self):
        self.setupStep(
            cvs.CVS(cvsroot=":pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot",
                    cvsmodule="mozilla/browser/", mode='full'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['cvs', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('uploadFile', dict(blocksize=32768, maxsize=None,
                                      workersrc='Root', workdir='wkdir/CVS',
                                      writer=ExpectRemoteRef(remotetransfer.StringFileWriter)))
            +
            Expect.behavior(
                uploadString(':pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot'))
            + 0,
            Expect('uploadFile', dict(blocksize=32768, maxsize=None,
                                      workersrc='Repository', workdir='wkdir/CVS',
                                      writer=ExpectRemoteRef(remotetransfer.StringFileWriter)))
            + Expect.behavior(uploadString('mozilla/browser/'))
            + 0,
            Expect('uploadFile', dict(blocksize=32768, maxsize=None,
                                      workersrc='Entries', workdir='wkdir/CVS',
                                      writer=ExpectRemoteRef(remotetransfer.StringFileWriter)))
            +
            Expect.behavior(uploadString('/file/1.1/Fri May 17 23:20:00//\nD'))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['cvsdiscard', '--ignore'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['cvs', '-z3', 'update', '-dP'])
            + 0,
        )

        self.expectOutcome(result=SUCCESS)
        self.expectProperty('got_revision', '2012-09-09 12:00:39 +0000', 'CVS')
        return self.runStep()

    def test_mode_incremental_with_options(self):
        step = cvs.CVS(cvsroot=":pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot",
                       cvsmodule="mozilla/browser/", mode='incremental',
                       global_options=['-q'], extra_options=['-l'])
        self.setupStep(step)
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['cvs', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('uploadFile', dict(blocksize=32768, maxsize=None,
                                      workersrc='Root', workdir='wkdir/CVS',
                                      writer=ExpectRemoteRef(remotetransfer.StringFileWriter)))
            + 1,
            Expect('rmdir', dict(dir='wkdir',
                                 logEnviron=True,
                                 timeout=step.timeout))
            + 0,
            ExpectShell(workdir='',
                        command=['cvs', '-q', '-d',
                                 ':pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot',
                                 '-z3', 'checkout', '-d', 'wkdir', '-l', 'mozilla/browser/'])
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty('got_revision', '2012-09-09 12:00:39 +0000', 'CVS')
        return self.runStep()

    def test_mode_incremental_with_env_logEnviron(self):
        self.setupStep(
            cvs.CVS(cvsroot=":pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot",
                    cvsmodule="mozilla/browser/", mode='incremental',
                    env={'abc': '123'}, logEnviron=False))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['cvs', '--version'],
                        env={'abc': '123'},
                        logEnviron=False)
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=False))
            + 1,
            Expect('uploadFile', dict(blocksize=32768, maxsize=None,
                                      workersrc='Root', workdir='wkdir/CVS',
                                      writer=ExpectRemoteRef(remotetransfer.StringFileWriter)))
            +
            Expect.behavior(
                uploadString(':pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot'))
            + 0,
            Expect('uploadFile', dict(blocksize=32768, maxsize=None,
                                      workersrc='Repository', workdir='wkdir/CVS',
                                      writer=ExpectRemoteRef(remotetransfer.StringFileWriter)))
            + Expect.behavior(uploadString('mozilla/browser/'))
            + 0,
            Expect('uploadFile', dict(blocksize=32768, maxsize=None,
                                      workersrc='Entries', workdir='wkdir/CVS',
                                      writer=ExpectRemoteRef(remotetransfer.StringFileWriter)))
            +
            Expect.behavior(uploadString('/file/1.1/Fri May 17 23:20:00//\nD'))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['cvs', '-z3', 'update', '-dP'],
                        env={'abc': '123'},
                        logEnviron=False)
            + 0,
        )

        self.expectOutcome(result=SUCCESS)
        self.expectProperty('got_revision', '2012-09-09 12:00:39 +0000', 'CVS')
        return self.runStep()

    def test_command_fails(self):
        self.setupStep(
            cvs.CVS(cvsroot=":pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot",
                    cvsmodule="mozilla/browser/", mode='incremental'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['cvs', '--version'])
            + 128,
        )

        self.expectOutcome(result=FAILURE)
        return self.runStep()

    def test_cvsdiscard_fails(self):
        self.setupStep(
            cvs.CVS(cvsroot=":pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot",
                    cvsmodule="mozilla/browser/", mode='full', method='fresh'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['cvs', '--version'])
            + 0,
            Expect('stat', dict(file='wkdir/.buildbot-patched',
                                logEnviron=True))
            + 1,
            Expect('uploadFile', dict(blocksize=32768, maxsize=None,
                                      workersrc='Root', workdir='wkdir/CVS',
                                      writer=ExpectRemoteRef(remotetransfer.StringFileWriter)))
            +
            Expect.behavior(
                uploadString(':pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot'))
            + 0,
            Expect('uploadFile', dict(blocksize=32768, maxsize=None,
                                      workersrc='Repository', workdir='wkdir/CVS',
                                      writer=ExpectRemoteRef(remotetransfer.StringFileWriter)))
            + Expect.behavior(uploadString('mozilla/browser/'))
            + 0,
            Expect('uploadFile', dict(blocksize=32768, maxsize=None,
                                      workersrc='Entries', workdir='wkdir/CVS',
                                      writer=ExpectRemoteRef(remotetransfer.StringFileWriter)))
            +
            Expect.behavior(uploadString('/file/1.1/Fri May 17 23:20:00//\nD'))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['cvsdiscard', '--ignore'])
            + ExpectShell.log('stdio',
                              stderr='FAIL!\n')
            + 1,
        )

        self.expectOutcome(result=FAILURE)
        return self.runStep()

    def test_worker_connection_lost(self):
        self.setupStep(
            cvs.CVS(cvsroot=":pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot",
                    cvsmodule="mozilla/browser/", mode='full', method='clean'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['cvs', '--version'])
            + ('err', error.ConnectionLost()),
        )

        self.expectOutcome(result=RETRY, state_string="update (retry)")
        return self.runStep()
