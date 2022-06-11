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

import time

from twisted.internet import error
from twisted.trial import unittest

from buildbot.process import remotetransfer
from buildbot.process.results import FAILURE
from buildbot.process.results import RETRY
from buildbot.process.results import SUCCESS
from buildbot.steps.source import cvs
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.steps import ExpectCpdir
from buildbot.test.steps import ExpectDownloadFile
from buildbot.test.steps import ExpectRemoteRef
from buildbot.test.steps import ExpectRmdir
from buildbot.test.steps import ExpectShell
from buildbot.test.steps import ExpectStat
from buildbot.test.steps import ExpectUploadFile
from buildbot.test.util import sourcesteps


class TestCVS(sourcesteps.SourceStepMixin, TestReactorMixin,
              unittest.TestCase):

    def setUp(self):
        self.setup_test_reactor()
        return self.setUpSourceStep()

    def tearDown(self):
        return self.tearDownSourceStep()

    def setup_step(self, step, *args, **kwargs):
        super().setup_step(step, *args, **kwargs)

        # make parseGotRevision return something consistent, patching the class
        # instead of the object since a new object is constructed by runTest.
        def parseGotRevision(self):
            self.updateSourceProperty('got_revision',
                                      '2012-09-09 12:00:39 +0000')
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

        step.parseGotRevision()
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
            '/file1/1.1/Fri May 17 23:20:00//\n'
            '/file2/1.1.2.3/Fri May 17 23:20:00//D2013.10.08.11.20.33\nD'), True)

    def test_mode_full_clean_and_login(self):
        self.setup_step(
            cvs.CVS(cvsroot=":pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot",
                    cvsmodule="mozilla/browser/", mode='full', method='clean',
                    login="a password"))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['cvs', '--version'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['cvs',
                                 '-d',
                                 ':pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot',
                                 'login'],
                        initial_stdin="a password\n")
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectUploadFile(blocksize=32768, maxsize=None,
                             workersrc='Root', workdir='wkdir/CVS',
                             writer=ExpectRemoteRef(remotetransfer.StringFileWriter))
            .upload_string(':pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot\n')
            .exit(0),
            ExpectUploadFile(blocksize=32768, maxsize=None,
                             workersrc='Repository', workdir='wkdir/CVS',
                             writer=ExpectRemoteRef(remotetransfer.StringFileWriter))
            .upload_string('mozilla/browser/\n')
            .exit(0),
            ExpectUploadFile(blocksize=32768, maxsize=None,
                             workersrc='Entries', workdir='wkdir/CVS',
                             writer=ExpectRemoteRef(remotetransfer.StringFileWriter))
            .upload_string('/file/1.1/Fri May 17 23:20:00//\nD\n')
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['cvsdiscard'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['cvs', '-z3', 'update', '-dP'])
            .exit(0)
        )

        self.expect_outcome(result=SUCCESS, state_string="update")
        self.expect_property('got_revision', '2012-09-09 12:00:39 +0000', 'CVS')
        return self.run_step()

    def test_mode_full_clean_and_login_worker_2_16(self):
        self.setup_step(
            cvs.CVS(cvsroot=":pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot",
                    cvsmodule="mozilla/browser/", mode='full', method='clean',
                    login="a password"),
            worker_version={'*': '2.16'})

        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['cvs', '--version'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['cvs',
                                 '-d',
                                 ':pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot',
                                 'login'],
                        initial_stdin="a password\n")
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectUploadFile(blocksize=32768, maxsize=None,
                             slavesrc='Root', workdir='wkdir/CVS',
                             writer=ExpectRemoteRef(remotetransfer.StringFileWriter))
            .upload_string(':pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot\n')
            .exit(0),
            ExpectUploadFile(blocksize=32768, maxsize=None,
                             slavesrc='Repository', workdir='wkdir/CVS',
                             writer=ExpectRemoteRef(remotetransfer.StringFileWriter))
            .upload_string('mozilla/browser/\n')
            .exit(0),
            ExpectUploadFile(blocksize=32768, maxsize=None,
                             slavesrc='Entries', workdir='wkdir/CVS',
                             writer=ExpectRemoteRef(remotetransfer.StringFileWriter))
            .upload_string('/file/1.1/Fri May 17 23:20:00//\nD\n')
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['cvsdiscard'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['cvs', '-z3', 'update', '-dP'])
            .exit(0)
        )

        self.expect_outcome(result=SUCCESS, state_string="update")
        self.expect_property('got_revision', '2012-09-09 12:00:39 +0000', 'CVS')
        return self.run_step()

    def test_mode_full_clean_patch(self):
        self.setup_step(
            cvs.CVS(cvsroot=":pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot",
                    cvsmodule="mozilla/browser/", mode='full', method='clean'),
            patch=(1, 'patch'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['cvs', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['cvsdiscard'])
            .exit(0),
            ExpectUploadFile(blocksize=32768, maxsize=None,
                             workersrc='Root', workdir='wkdir/CVS',
                             writer=ExpectRemoteRef(remotetransfer.StringFileWriter))
            .upload_string(':pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot\n')
            .exit(0),
            ExpectUploadFile(blocksize=32768, maxsize=None,
                             workersrc='Repository', workdir='wkdir/CVS',
                             writer=ExpectRemoteRef(remotetransfer.StringFileWriter))
            .upload_string('mozilla/browser/\n')
            .exit(0),
            ExpectUploadFile(blocksize=32768, maxsize=None,
                             workersrc='Entries', workdir='wkdir/CVS',
                             writer=ExpectRemoteRef(remotetransfer.StringFileWriter))
            .upload_string('/file/1.1/Fri May 17 23:20:00//\nD\n')
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['cvsdiscard'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['cvs', '-z3', 'update', '-dP'])
            .exit(0),
            ExpectDownloadFile(blocksize=32768, maxsize=None,
                               reader=ExpectRemoteRef(remotetransfer.StringFileReader),
                               workerdest='.buildbot-diff', workdir='wkdir', mode=None)
            .exit(0),
            ExpectDownloadFile(blocksize=32768, maxsize=None,
                               reader=ExpectRemoteRef(remotetransfer.StringFileReader),
                               workerdest='.buildbot-patched', workdir='wkdir', mode=None)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['patch', '-p1', '--remove-empty-files',
                                 '--force', '--forward', '-i', '.buildbot-diff'])
            .exit(0),
            ExpectRmdir(dir='wkdir/.buildbot-diff', log_environ=True)
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property('got_revision', '2012-09-09 12:00:39 +0000', 'CVS')
        return self.run_step()

    def test_mode_full_clean_patch_worker_2_16(self):
        self.setup_step(
            cvs.CVS(cvsroot=":pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot",
                    cvsmodule="mozilla/browser/", mode='full', method='clean'),
            patch=(1, 'patch'),
            worker_version={'*': '2.16'})
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['cvs', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['cvsdiscard'])
            .exit(0),
            ExpectUploadFile(blocksize=32768, maxsize=None,
                             slavesrc='Root', workdir='wkdir/CVS',
                             writer=ExpectRemoteRef(remotetransfer.StringFileWriter))
            .upload_string(':pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot\n')
            .exit(0),
            ExpectUploadFile(blocksize=32768, maxsize=None,
                             slavesrc='Repository', workdir='wkdir/CVS',
                             writer=ExpectRemoteRef(remotetransfer.StringFileWriter))
            .upload_string('mozilla/browser/\n')
            .exit(0),
            ExpectUploadFile(blocksize=32768, maxsize=None,
                             slavesrc='Entries', workdir='wkdir/CVS',
                             writer=ExpectRemoteRef(remotetransfer.StringFileWriter))
            .upload_string('/file/1.1/Fri May 17 23:20:00//\nD\n')
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['cvsdiscard'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['cvs', '-z3', 'update', '-dP'])
            .exit(0),
            ExpectDownloadFile(blocksize=32768, maxsize=None,
                               reader=ExpectRemoteRef(remotetransfer.StringFileReader),
                               slavedest='.buildbot-diff', workdir='wkdir', mode=None)
            .exit(0),
            ExpectDownloadFile(blocksize=32768, maxsize=None,
                               reader=ExpectRemoteRef(remotetransfer.StringFileReader),
                               slavedest='.buildbot-patched', workdir='wkdir', mode=None)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['patch', '-p1', '--remove-empty-files',
                                 '--force', '--forward', '-i', '.buildbot-diff'])
            .exit(0),
            ExpectRmdir(dir='wkdir/.buildbot-diff', log_environ=True)
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property('got_revision', '2012-09-09 12:00:39 +0000', 'CVS')
        return self.run_step()

    def test_mode_full_clean_timeout(self):
        self.setup_step(
            cvs.CVS(cvsroot=":pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot",
                    cvsmodule="mozilla/browser/", mode='full', method='clean',
                    timeout=1))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        timeout=1,
                        command=['cvs', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectUploadFile(blocksize=32768, maxsize=None,
                             workersrc='Root', workdir='wkdir/CVS',
                             writer=ExpectRemoteRef(remotetransfer.StringFileWriter))
            .upload_string(':pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot\n')
            .exit(0),
            ExpectUploadFile(blocksize=32768, maxsize=None,
                             workersrc='Repository', workdir='wkdir/CVS',
                             writer=ExpectRemoteRef(remotetransfer.StringFileWriter))
            .upload_string('mozilla/browser/\n')
            .exit(0),
            ExpectUploadFile(blocksize=32768, maxsize=None,
                             workersrc='Entries', workdir='wkdir/CVS',
                             writer=ExpectRemoteRef(remotetransfer.StringFileWriter))
            .upload_string('/file/1.1/Fri May 17 23:20:00//\nD\n')
            .exit(0),
            ExpectShell(workdir='wkdir',
                        timeout=1,
                        command=['cvsdiscard'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        timeout=1,
                        command=['cvs', '-z3', 'update', '-dP'])
            .exit(0)
        )

        self.expect_outcome(result=SUCCESS)
        self.expect_property('got_revision', '2012-09-09 12:00:39 +0000', 'CVS')
        return self.run_step()

    def test_mode_full_clean_branch(self):
        self.setup_step(
            cvs.CVS(cvsroot=":pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot",
                    cvsmodule="mozilla/browser/", mode='full', method='clean',
                    branch='branch'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['cvs', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectUploadFile(blocksize=32768, maxsize=None,
                             workersrc='Root', workdir='wkdir/CVS',
                             writer=ExpectRemoteRef(remotetransfer.StringFileWriter))
            .upload_string(':pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot\n')
            .exit(0),
            ExpectUploadFile(blocksize=32768, maxsize=None,
                             workersrc='Repository', workdir='wkdir/CVS',
                             writer=ExpectRemoteRef(remotetransfer.StringFileWriter))
            .upload_string('mozilla/browser/\n')
            .exit(0),
            ExpectUploadFile(blocksize=32768, maxsize=None,
                             workersrc='Entries', workdir='wkdir/CVS',
                             writer=ExpectRemoteRef(remotetransfer.StringFileWriter))
            .upload_string('/file/1.1/Fri May 17 23:20:00//\nD\n')
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['cvsdiscard'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['cvs', '-z3', 'update', '-dP', '-r', 'branch'])
            .exit(0)
        )

        self.expect_outcome(result=SUCCESS)
        self.expect_property('got_revision', '2012-09-09 12:00:39 +0000', 'CVS')
        return self.run_step()

    def test_mode_full_clean_branch_sourcestamp(self):
        self.setup_step(
            cvs.CVS(cvsroot=":pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot",
                    cvsmodule="mozilla/browser/", mode='full', method='clean'),
            args={'branch': 'my_branch'})
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['cvs', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectUploadFile(blocksize=32768, maxsize=None,
                             workersrc='Root', workdir='wkdir/CVS',
                             writer=ExpectRemoteRef(remotetransfer.StringFileWriter))
            .upload_string(':pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot\n')
            .exit(0),
            ExpectUploadFile(blocksize=32768, maxsize=None,
                             workersrc='Repository', workdir='wkdir/CVS',
                             writer=ExpectRemoteRef(remotetransfer.StringFileWriter))
            .upload_string('mozilla/browser/\n')
            .exit(0),
            ExpectUploadFile(blocksize=32768, maxsize=None,
                             workersrc='Entries', workdir='wkdir/CVS',
                             writer=ExpectRemoteRef(remotetransfer.StringFileWriter))
            .upload_string('/file/1.1/Fri May 17 23:20:00//\nD\n')
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['cvsdiscard'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['cvs', '-z3', 'update', '-dP', '-r', 'my_branch'])
            .exit(0)
        )

        self.expect_outcome(result=SUCCESS)
        self.expect_property('got_revision', '2012-09-09 12:00:39 +0000', 'CVS')
        return self.run_step()

    def test_mode_full_fresh(self):
        self.setup_step(
            cvs.CVS(cvsroot=":pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot",
                    cvsmodule="mozilla/browser/", mode='full', method='fresh'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['cvs', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectUploadFile(blocksize=32768, maxsize=None,
                             workersrc='Root', workdir='wkdir/CVS',
                             writer=ExpectRemoteRef(remotetransfer.StringFileWriter))
            .upload_string(':pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot\n')
            .exit(0),
            ExpectUploadFile(blocksize=32768, maxsize=None,
                             workersrc='Repository', workdir='wkdir/CVS',
                             writer=ExpectRemoteRef(remotetransfer.StringFileWriter))
            .upload_string('mozilla/browser/\n')
            .exit(0),
            ExpectUploadFile(blocksize=32768, maxsize=None,
                             workersrc='Entries', workdir='wkdir/CVS',
                             writer=ExpectRemoteRef(remotetransfer.StringFileWriter))
            .upload_string('/file/1.1/Fri May 17 23:20:00//\nD\n')
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['cvsdiscard', '--ignore'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['cvs', '-z3', 'update', '-dP'])
            .exit(0)
        )

        self.expect_outcome(result=SUCCESS)
        self.expect_property('got_revision', '2012-09-09 12:00:39 +0000', 'CVS')
        return self.run_step()

    def test_mode_full_clobber(self):
        step = cvs.CVS(cvsroot=":pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot",
                       cvsmodule="mozilla/browser/", mode='full', method='clobber')
        self.setup_step(step)
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['cvs', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectRmdir(dir='wkdir', log_environ=True, timeout=step.timeout)
            .exit(0),
            ExpectShell(workdir='',
                        command=['cvs',
                                 '-d',
                                 ':pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot',
                                 '-z3', 'checkout', '-d', 'wkdir', 'mozilla/browser/'])
            .exit(0)
        )

        self.expect_outcome(result=SUCCESS)
        self.expect_property('got_revision', '2012-09-09 12:00:39 +0000', 'CVS')
        return self.run_step()

    def test_mode_full_clobber_retry(self):
        step = cvs.CVS(cvsroot=":pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot",
                       cvsmodule="mozilla/browser/", mode='full', method='clobber',
                       retry=(0, 2))
        self.setup_step(step)
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['cvs', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectRmdir(dir='wkdir', log_environ=True, timeout=step.timeout)
            .exit(0),
            ExpectShell(workdir='',
                        command=['cvs',
                                 '-d',
                                 ':pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot',
                                 '-z3', 'checkout', '-d', 'wkdir', 'mozilla/browser/'])
            .exit(1),
            ExpectRmdir(dir='wkdir', log_environ=True, timeout=step.timeout)
            .exit(0),
            ExpectShell(workdir='',
                        command=['cvs',
                                 '-d',
                                 ':pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot',
                                 '-z3', 'checkout', '-d', 'wkdir', 'mozilla/browser/'])
            .exit(1),
            ExpectRmdir(dir='wkdir', log_environ=True, timeout=step.timeout)
            .exit(0),
            ExpectShell(workdir='',
                        command=['cvs',
                                 '-d',
                                 ':pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot',
                                 '-z3', 'checkout', '-d', 'wkdir', 'mozilla/browser/'])
            .exit(0)
        )

        self.expect_outcome(result=SUCCESS)
        self.expect_property('got_revision', '2012-09-09 12:00:39 +0000', 'CVS')
        return self.run_step()

    def test_mode_full_copy(self):
        step = cvs.CVS(cvsroot=":pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot",
                       cvsmodule="mozilla/browser/", mode='full', method='copy')
        self.setup_step(step)
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['cvs', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectRmdir(dir='wkdir', log_environ=True, timeout=step.timeout)
            .exit(0),
            ExpectUploadFile(blocksize=32768, maxsize=None,
                             workersrc='Root', workdir='source/CVS',
                             writer=ExpectRemoteRef(remotetransfer.StringFileWriter))
            .upload_string(':pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot\n')
            .exit(0),
            ExpectUploadFile(blocksize=32768, maxsize=None,
                             workersrc='Repository', workdir='source/CVS',
                             writer=ExpectRemoteRef(remotetransfer.StringFileWriter))
            .upload_string('mozilla/browser/\n')
            .exit(0),
            ExpectUploadFile(blocksize=32768, maxsize=None,
                             workersrc='Entries', workdir='source/CVS',
                             writer=ExpectRemoteRef(remotetransfer.StringFileWriter))
            .upload_string('/file/1.1/Fri May 17 23:20:00//\nD\n')
            .exit(0),
            ExpectShell(workdir='source',
                        command=['cvs', '-z3', 'update', '-dP'])
            .exit(0),
            ExpectCpdir(fromdir='source', todir='wkdir', log_environ=True, timeout=step.timeout)
            .exit(0)
        )

        self.expect_outcome(result=SUCCESS)
        self.expect_property('got_revision', '2012-09-09 12:00:39 +0000', 'CVS')
        return self.run_step()

    def test_mode_full_copy_wrong_repo(self):
        step = cvs.CVS(cvsroot=":pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot",
                       cvsmodule="mozilla/browser/", mode='full', method='copy')
        self.setup_step(step)
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['cvs', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectRmdir(dir='wkdir', log_environ=True, timeout=step.timeout)
            .exit(0),
            ExpectUploadFile(blocksize=32768, maxsize=None,
                             workersrc='Root', workdir='source/CVS',
                             writer=ExpectRemoteRef(remotetransfer.StringFileWriter))
            .upload_string('the-end-of-the-universe\n')
            .exit(0),
            ExpectRmdir(dir='source', log_environ=True, timeout=step.timeout)
            .exit(0),
            ExpectShell(workdir='',
                        command=['cvs',
                                 '-d',
                                 ':pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot',
                                 '-z3', 'checkout', '-d', 'source', 'mozilla/browser/'])
            .exit(0),
            ExpectCpdir(fromdir='source', todir='wkdir', log_environ=True, timeout=step.timeout)
            .exit(0)
        )

        self.expect_outcome(result=SUCCESS)
        self.expect_property('got_revision', '2012-09-09 12:00:39 +0000', 'CVS')
        return self.run_step()

    def test_mode_incremental(self):
        self.setup_step(
            cvs.CVS(cvsroot=":pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot",
                    cvsmodule="mozilla/browser/", mode='incremental'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['cvs', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectUploadFile(blocksize=32768, maxsize=None,
                             workersrc='Root', workdir='wkdir/CVS',
                             writer=ExpectRemoteRef(remotetransfer.StringFileWriter))
            .upload_string(':pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot\n')
            .exit(0),
            ExpectUploadFile(blocksize=32768, maxsize=None,
                             workersrc='Repository', workdir='wkdir/CVS',
                             writer=ExpectRemoteRef(remotetransfer.StringFileWriter))
            .upload_string('mozilla/browser/\n')
            .exit(0),
            ExpectUploadFile(blocksize=32768, maxsize=None,
                             workersrc='Entries', workdir='wkdir/CVS',
                             writer=ExpectRemoteRef(remotetransfer.StringFileWriter))
            .upload_string('/file/1.1/Fri May 17 23:20:00//\nD\n')
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['cvs', '-z3', 'update', '-dP'])
            .exit(0)
        )

        self.expect_outcome(result=SUCCESS)
        self.expect_property('got_revision', '2012-09-09 12:00:39 +0000', 'CVS')
        return self.run_step()

    def test_mode_incremental_sticky_date(self):
        step = cvs.CVS(cvsroot=":pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot",
                       cvsmodule="mozilla/browser/", mode='incremental')
        self.setup_step(step)
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['cvs', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectUploadFile(blocksize=32768, maxsize=None,
                             workersrc='Root', workdir='wkdir/CVS',
                             writer=ExpectRemoteRef(remotetransfer.StringFileWriter))
            .upload_string(':pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot\n')
            .exit(0),
            ExpectUploadFile(blocksize=32768, maxsize=None,
                             workersrc='Repository', workdir='wkdir/CVS',
                             writer=ExpectRemoteRef(remotetransfer.StringFileWriter))
            .upload_string('mozilla/browser/\n')
            .exit(0),
            ExpectUploadFile(blocksize=32768, maxsize=None,
                             workersrc='Entries', workdir='wkdir/CVS',
                             writer=ExpectRemoteRef(remotetransfer.StringFileWriter))
            .upload_string('/file/1.1/Fri May 17 23:20:00//D2013.10.08.11.20.33\nD\n')
            .exit(0),
            ExpectRmdir(dir='wkdir', log_environ=True, timeout=step.timeout)
            .exit(0),
            ExpectShell(workdir='',
                        command=['cvs',
                                 '-d',
                                 ':pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot',
                                 '-z3', 'checkout', '-d', 'wkdir', 'mozilla/browser/'])
            .exit(0)
        )

        self.expect_outcome(result=SUCCESS)
        self.expect_property('got_revision', '2012-09-09 12:00:39 +0000', 'CVS')
        return self.run_step()

    def test_mode_incremental_password_windows(self):
        self.setup_step(
            cvs.CVS(cvsroot=":pserver:dustin:secrets@cvs-mirror.mozilla.org:/cvsroot",
                    cvsmodule="mozilla/browser/", mode='incremental'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['cvs', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectUploadFile(blocksize=32768, maxsize=None,
                             workersrc='Root', workdir='wkdir/CVS',
                             writer=ExpectRemoteRef(remotetransfer.StringFileWriter))
            # on Windows, this file does not contain the password, per
            # http://trac.buildbot.net/ticket/2355
            .upload_string(':pserver:dustin@cvs-mirror.mozilla.org:/cvsroot\n')
            .exit(0),
            ExpectUploadFile(blocksize=32768, maxsize=None,
                             workersrc='Repository', workdir='wkdir/CVS',
                             writer=ExpectRemoteRef(remotetransfer.StringFileWriter))
            .upload_string('mozilla/browser/\n')
            .exit(0),
            ExpectUploadFile(blocksize=32768, maxsize=None,
                             workersrc='Entries', workdir='wkdir/CVS',
                             writer=ExpectRemoteRef(remotetransfer.StringFileWriter))
            .upload_string('/file/1.1/Fri May 17 23:20:00//\nD\n')
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['cvs', '-z3', 'update', '-dP'])
            .exit(0)
        )

        self.expect_outcome(result=SUCCESS)
        return self.run_step()

    def test_mode_incremental_branch(self):
        self.setup_step(
            cvs.CVS(cvsroot=":pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot",
                    cvsmodule="mozilla/browser/", mode='incremental',
                    branch='my_branch'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['cvs', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectUploadFile(blocksize=32768, maxsize=None,
                             workersrc='Root', workdir='wkdir/CVS',
                             writer=ExpectRemoteRef(remotetransfer.StringFileWriter))
            .upload_string(':pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot\n')
            .exit(0),
            ExpectUploadFile(blocksize=32768, maxsize=None,
                             workersrc='Repository', workdir='wkdir/CVS',
                             writer=ExpectRemoteRef(remotetransfer.StringFileWriter))
            .upload_string('mozilla/browser/\n')
            .exit(0),
            ExpectUploadFile(blocksize=32768, maxsize=None,
                             workersrc='Entries', workdir='wkdir/CVS',
                             writer=ExpectRemoteRef(remotetransfer.StringFileWriter))
            .upload_string('/file/1.1/Fri May 17 23:20:00//\nD\n')
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['cvs', '-z3', 'update', '-dP', '-r', 'my_branch'])
            .exit(0)
        )

        self.expect_outcome(result=SUCCESS)
        self.expect_property('got_revision', '2012-09-09 12:00:39 +0000', 'CVS')
        return self.run_step()

    def test_mode_incremental_special_case(self):
        self.setup_step(
            cvs.CVS(cvsroot=":pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot",
                    cvsmodule="mozilla/browser/", mode='incremental',
                    branch='HEAD'),
            args=dict(revision='2012-08-16 16:05:16 +0000'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['cvs', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectUploadFile(blocksize=32768, maxsize=None,
                             workersrc='Root', workdir='wkdir/CVS',
                             writer=ExpectRemoteRef(remotetransfer.StringFileWriter))
            .upload_string(':pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot\n')
            .exit(0),
            ExpectUploadFile(blocksize=32768, maxsize=None,
                             workersrc='Repository', workdir='wkdir/CVS',
                             writer=ExpectRemoteRef(remotetransfer.StringFileWriter))
            .upload_string('mozilla/browser/\n')
            .exit(0),
            ExpectUploadFile(blocksize=32768, maxsize=None,
                             workersrc='Entries', workdir='wkdir/CVS',
                             writer=ExpectRemoteRef(remotetransfer.StringFileWriter))
            .upload_string('/file/1.1/Fri May 17 23:20:00//\nD\n')
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['cvs', '-z3', 'update', '-dP',
                                 # note, no -r HEAD here - that's the special
                                 # case
                                 '-D', '2012-08-16 16:05:16 +0000'])
            .exit(0)
        )

        self.expect_outcome(result=SUCCESS)
        return self.run_step()

    def test_mode_incremental_branch_sourcestamp(self):
        self.setup_step(
            cvs.CVS(cvsroot=":pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot",
                    cvsmodule="mozilla/browser/", mode='incremental'),
            args={'branch': 'my_branch'})
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['cvs', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectUploadFile(blocksize=32768, maxsize=None,
                             workersrc='Root', workdir='wkdir/CVS',
                             writer=ExpectRemoteRef(remotetransfer.StringFileWriter))
            .upload_string(':pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot\n')
            .exit(0),
            ExpectUploadFile(blocksize=32768, maxsize=None,
                             workersrc='Repository', workdir='wkdir/CVS',
                             writer=ExpectRemoteRef(remotetransfer.StringFileWriter))
            .upload_string('mozilla/browser/\n')
            .exit(0),
            ExpectUploadFile(blocksize=32768, maxsize=None,
                             workersrc='Entries', workdir='wkdir/CVS',
                             writer=ExpectRemoteRef(remotetransfer.StringFileWriter))
            .upload_string('/file/1.1/Fri May 17 23:20:00//\nD\n')
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['cvs', '-z3', 'update', '-dP', '-r', 'my_branch'])
            .exit(0)
        )

        self.expect_outcome(result=SUCCESS)
        self.expect_property('got_revision', '2012-09-09 12:00:39 +0000', 'CVS')
        return self.run_step()

    def test_mode_incremental_not_loggedin(self):
        self.setup_step(
            cvs.CVS(cvsroot=":pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot",
                    cvsmodule="mozilla/browser/", mode='incremental'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['cvs', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectUploadFile(blocksize=32768, maxsize=None,
                             workersrc='Root', workdir='wkdir/CVS',
                             writer=ExpectRemoteRef(remotetransfer.StringFileWriter))
            .upload_string(':pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot\n')
            .exit(0),
            ExpectUploadFile(blocksize=32768, maxsize=None,
                             workersrc='Repository', workdir='wkdir/CVS',
                             writer=ExpectRemoteRef(remotetransfer.StringFileWriter))
            .upload_string('mozilla/browser/\n')
            .exit(0),
            ExpectUploadFile(blocksize=32768, maxsize=None,
                             workersrc='Entries', workdir='wkdir/CVS',
                             writer=ExpectRemoteRef(remotetransfer.StringFileWriter))
            .upload_string('/file/1.1/Fri May 17 23:20:00//\nD\n')
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['cvs', '-z3', 'update', '-dP'])
            .exit(0)
        )

        self.expect_outcome(result=SUCCESS)
        self.expect_property('got_revision', '2012-09-09 12:00:39 +0000', 'CVS')
        return self.run_step()

    def test_mode_incremental_no_existing_repo(self):
        step = cvs.CVS(cvsroot=":pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot",
                       cvsmodule="mozilla/browser/", mode='incremental')
        self.setup_step(step)
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['cvs', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectUploadFile(blocksize=32768, maxsize=None,
                             workersrc='Root', workdir='wkdir/CVS',
                             writer=ExpectRemoteRef(remotetransfer.StringFileWriter))
            .exit(1),
            ExpectRmdir(dir='wkdir', log_environ=True, timeout=step.timeout)
            .exit(0),
            ExpectShell(workdir='',
                        command=['cvs',
                                 '-d',
                                 ':pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot',
                                 '-z3', 'checkout', '-d', 'wkdir', 'mozilla/browser/'])
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property('got_revision', '2012-09-09 12:00:39 +0000', 'CVS')
        return self.run_step()

    def test_mode_incremental_retry(self):
        step = cvs.CVS(cvsroot=":pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot",
                       cvsmodule="mozilla/browser/", mode='incremental',
                       retry=(0, 1))
        self.setup_step(step)
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['cvs', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectUploadFile(blocksize=32768, maxsize=None,
                             workersrc='Root', workdir='wkdir/CVS',
                             writer=ExpectRemoteRef(remotetransfer.StringFileWriter))
            .exit(1),
            ExpectRmdir(dir='wkdir', log_environ=True, timeout=step.timeout)
            .exit(0),
            ExpectShell(workdir='',
                        command=['cvs',
                                 '-d',
                                 ':pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot',
                                 '-z3', 'checkout', '-d', 'wkdir', 'mozilla/browser/'])
            .exit(1),
            ExpectRmdir(dir='wkdir', log_environ=True, timeout=step.timeout)
            .exit(0),
            ExpectShell(workdir='',
                        command=['cvs',
                                 '-d',
                                 ':pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot',
                                 '-z3', 'checkout', '-d', 'wkdir', 'mozilla/browser/'])
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property('got_revision', '2012-09-09 12:00:39 +0000', 'CVS')
        return self.run_step()

    def test_mode_incremental_wrong_repo(self):
        step = cvs.CVS(cvsroot=":pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot",
                       cvsmodule="mozilla/browser/", mode='incremental')
        self.setup_step(step)
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['cvs', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectUploadFile(blocksize=32768, maxsize=None,
                             workersrc='Root', workdir='wkdir/CVS',
                             writer=ExpectRemoteRef(remotetransfer.StringFileWriter))
            .upload_string('the-end-of-the-universe\n')
            .exit(0),
            ExpectRmdir(dir='wkdir', log_environ=True, timeout=step.timeout)
            .exit(0),
            ExpectShell(workdir='',
                        command=['cvs',
                                 '-d',
                                 ':pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot',
                                 '-z3', 'checkout', '-d', 'wkdir', 'mozilla/browser/'])
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property('got_revision', '2012-09-09 12:00:39 +0000', 'CVS')
        return self.run_step()

    def test_mode_incremental_wrong_module(self):
        step = cvs.CVS(cvsroot=":pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot",
                       cvsmodule="mozilla/browser/", mode='incremental')
        self.setup_step(step)
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['cvs', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectUploadFile(blocksize=32768, maxsize=None,
                             workersrc='Root', workdir='wkdir/CVS',
                             writer=ExpectRemoteRef(remotetransfer.StringFileWriter))
            .upload_string(':pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot\n')
            .exit(0),
            ExpectUploadFile(blocksize=32768, maxsize=None,
                             workersrc='Repository', workdir='wkdir/CVS',
                             writer=ExpectRemoteRef(remotetransfer.StringFileWriter))
            .upload_string('the-end-of-the-universe\n')
            .exit(0),
            ExpectRmdir(dir='wkdir', log_environ=True, timeout=step.timeout)
            .exit(0),
            ExpectShell(workdir='',
                        command=['cvs',
                                 '-d',
                                 ':pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot',
                                 '-z3', 'checkout', '-d', 'wkdir', 'mozilla/browser/'])
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property('got_revision', '2012-09-09 12:00:39 +0000', 'CVS')
        return self.run_step()

    def test_mode_full_clean_no_existing_repo(self):
        self.setup_step(
            cvs.CVS(cvsroot=":pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot",
                    cvsmodule="mozilla/browser/", mode='full', method='clean'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['cvs', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectUploadFile(blocksize=32768, maxsize=None,
                             workersrc='Root', workdir='wkdir/CVS',
                             writer=ExpectRemoteRef(remotetransfer.StringFileWriter))
            .exit(1),
            ExpectShell(workdir='',
                        command=['cvs',
                                 '-d',
                                 ':pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot',
                                 '-z3', 'checkout', '-d', 'wkdir', 'mozilla/browser/'])
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property('got_revision', '2012-09-09 12:00:39 +0000', 'CVS')
        return self.run_step()

    def test_mode_full_clean_wrong_repo(self):
        self.setup_step(
            cvs.CVS(cvsroot=":pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot",
                    cvsmodule="mozilla/browser/", mode='full', method='clean'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['cvs', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectUploadFile(blocksize=32768, maxsize=None,
                             workersrc='Root', workdir='wkdir/CVS',
                             writer=ExpectRemoteRef(remotetransfer.StringFileWriter))
            .upload_string('the-end-of-the-universe\n')
            .exit(0),
            ExpectShell(workdir='',
                        command=['cvs',
                                 '-d',
                                 ':pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot',
                                 '-z3', 'checkout', '-d', 'wkdir', 'mozilla/browser/'])
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property('got_revision', '2012-09-09 12:00:39 +0000', 'CVS')
        return self.run_step()

    def test_mode_full_no_method(self):
        self.setup_step(
            cvs.CVS(cvsroot=":pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot",
                    cvsmodule="mozilla/browser/", mode='full'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['cvs', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectUploadFile(blocksize=32768, maxsize=None,
                             workersrc='Root', workdir='wkdir/CVS',
                             writer=ExpectRemoteRef(remotetransfer.StringFileWriter))
            .upload_string(':pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot\n')
            .exit(0),
            ExpectUploadFile(blocksize=32768, maxsize=None,
                             workersrc='Repository', workdir='wkdir/CVS',
                             writer=ExpectRemoteRef(remotetransfer.StringFileWriter))
            .upload_string('mozilla/browser/\n')
            .exit(0),
            ExpectUploadFile(blocksize=32768, maxsize=None,
                             workersrc='Entries', workdir='wkdir/CVS',
                             writer=ExpectRemoteRef(remotetransfer.StringFileWriter))
            .upload_string('/file/1.1/Fri May 17 23:20:00//\nD\n')
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['cvsdiscard', '--ignore'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['cvs', '-z3', 'update', '-dP'])
            .exit(0)
        )

        self.expect_outcome(result=SUCCESS)
        self.expect_property('got_revision', '2012-09-09 12:00:39 +0000', 'CVS')
        return self.run_step()

    def test_mode_incremental_with_options(self):
        step = cvs.CVS(cvsroot=":pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot",
                       cvsmodule="mozilla/browser/", mode='incremental',
                       global_options=['-q'], extra_options=['-l'])
        self.setup_step(step)
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['cvs', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectUploadFile(blocksize=32768, maxsize=None,
                             workersrc='Root', workdir='wkdir/CVS',
                             writer=ExpectRemoteRef(remotetransfer.StringFileWriter))
            .exit(1),
            ExpectRmdir(dir='wkdir', log_environ=True, timeout=step.timeout)
            .exit(0),
            ExpectShell(workdir='',
                        command=['cvs', '-q', '-d',
                                 ':pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot',
                                 '-z3', 'checkout', '-d', 'wkdir', '-l', 'mozilla/browser/'])
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property('got_revision', '2012-09-09 12:00:39 +0000', 'CVS')
        return self.run_step()

    def test_mode_incremental_with_env_log_environ(self):
        self.setup_step(
            cvs.CVS(cvsroot=":pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot",
                    cvsmodule="mozilla/browser/", mode='incremental',
                    env={'abc': '123'}, logEnviron=False))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['cvs', '--version'],
                        env={'abc': '123'},
                        log_environ=False)
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=False)
            .exit(1),
            ExpectUploadFile(blocksize=32768, maxsize=None,
                             workersrc='Root', workdir='wkdir/CVS',
                             writer=ExpectRemoteRef(remotetransfer.StringFileWriter))
            .upload_string(':pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot\n')
            .exit(0),
            ExpectUploadFile(blocksize=32768, maxsize=None,
                             workersrc='Repository', workdir='wkdir/CVS',
                             writer=ExpectRemoteRef(remotetransfer.StringFileWriter))
            .upload_string('mozilla/browser/\n')
            .exit(0),
            ExpectUploadFile(blocksize=32768, maxsize=None,
                             workersrc='Entries', workdir='wkdir/CVS',
                             writer=ExpectRemoteRef(remotetransfer.StringFileWriter))
            .upload_string('/file/1.1/Fri May 17 23:20:00//\nD\n')
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['cvs', '-z3', 'update', '-dP'],
                        env={'abc': '123'},
                        log_environ=False)
            .exit(0)
        )

        self.expect_outcome(result=SUCCESS)
        self.expect_property('got_revision', '2012-09-09 12:00:39 +0000', 'CVS')
        return self.run_step()

    def test_command_fails(self):
        self.setup_step(
            cvs.CVS(cvsroot=":pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot",
                    cvsmodule="mozilla/browser/", mode='incremental'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['cvs', '--version'])
            .exit(128)
        )

        self.expect_outcome(result=FAILURE)
        return self.run_step()

    def test_cvsdiscard_fails(self):
        self.setup_step(
            cvs.CVS(cvsroot=":pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot",
                    cvsmodule="mozilla/browser/", mode='full', method='fresh'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['cvs', '--version'])
            .exit(0),
            ExpectStat(file='wkdir/.buildbot-patched', log_environ=True)
            .exit(1),
            ExpectUploadFile(blocksize=32768, maxsize=None,
                             workersrc='Root', workdir='wkdir/CVS',
                             writer=ExpectRemoteRef(remotetransfer.StringFileWriter))
            .upload_string(':pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot\n')
            .exit(0),
            ExpectUploadFile(blocksize=32768, maxsize=None,
                             workersrc='Repository', workdir='wkdir/CVS',
                             writer=ExpectRemoteRef(remotetransfer.StringFileWriter))
            .upload_string('mozilla/browser/\n')
            .exit(0),
            ExpectUploadFile(blocksize=32768, maxsize=None,
                             workersrc='Entries', workdir='wkdir/CVS',
                             writer=ExpectRemoteRef(remotetransfer.StringFileWriter))
            .upload_string('/file/1.1/Fri May 17 23:20:00//\nD\n')
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['cvsdiscard', '--ignore'])
            .stderr('FAIL!\n')
            .exit(1)
        )

        self.expect_outcome(result=FAILURE)
        return self.run_step()

    def test_worker_connection_lost(self):
        self.setup_step(
            cvs.CVS(cvsroot=":pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot",
                    cvsmodule="mozilla/browser/", mode='full', method='clean'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['cvs', '--version'])
            .error(error.ConnectionLost())
        )

        self.expect_outcome(result=RETRY, state_string="update (retry)")
        return self.run_step()
