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

from twisted.trial import unittest
from buildbot.steps.source import cvs
from buildbot.status.results import SUCCESS
from buildbot.test.util import sourcesteps
from buildbot.test.fake.remotecommand import ExpectShell, ExpectLogged

class TestCVS(sourcesteps.SourceStepMixin, unittest.TestCase):

    def setUp(self):
        return self.setUpSourceStep()

    def tearDown(self):
        return self.tearDownSourceStep()

    def test_mode_full_clean(self):
        self.setupStep(
            cvs.CVS(cvsroot=":pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot",
                    cvsmodule="mozilla/browser/", mode='full', method='clean',
                    login=True))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['cvs', '--version'])
            + 0,
            ExpectLogged('stat', dict(file='wkdir/CVS',
                                      logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['cvsdiscard'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['cvs', '-z3', 'update', '-dP'])
            + 0,
            )

        self.expectOutcome(result=SUCCESS, status_text=["update"])
        return self.runStep()

    def test_mode_full_fresh(self):
        self.setupStep(
            cvs.CVS(cvsroot=":pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot",
                    cvsmodule="mozilla/browser/", mode='full', method='fresh',
                    login=True))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['cvs', '--version'])
            + 0,
            ExpectLogged('stat', dict(file='wkdir/CVS',
                                      logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['cvsdiscard', '--ignore'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['cvs', '-z3', 'update', '-dP'])
            + 0,
            )

        self.expectOutcome(result=SUCCESS, status_text=["update"])
        return self.runStep()

    def test_mode_full_clobber(self):
        self.setupStep(
            cvs.CVS(cvsroot=":pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot",
                    cvsmodule="mozilla/browser/", mode='full', method='clobber',
                    login=True))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['cvs', '--version'])
            + 0,
            ExpectLogged('rmdir', dict(dir='wkdir',
                                       logEnviron=True))
            + 0,
            ExpectShell(workdir='',
                        command=['cvs',
                                 '-d',
                                 ':pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot',
                                 '-z3', 'checkout', '-d', 'wkdir', 'mozilla/browser/'])
            + 0,
            )

        self.expectOutcome(result=SUCCESS, status_text=["update"])
        return self.runStep()

    def test_mode_full_copy(self):
        self.setupStep(
            cvs.CVS(cvsroot=":pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot",
                    cvsmodule="mozilla/browser/", mode='full', method='copy',
                    login=True))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['cvs', '--version'])
            + 0,
            ExpectLogged('rmdir', dict(dir='wkdir',
                                       logEnviron=True))
            + 0,
            ExpectLogged('stat', dict(file='source/CVS',
                                      logEnviron=True))
            + 0,            
            ExpectShell(workdir='source',
                        command=['cvs', '-z3', 'update', '-dP'])
            + 0,
            ExpectLogged('cpdir', {'fromdir': 'source', 'todir': 'build',
                                   'logEnviron': True})
            + 0,
            )

        self.expectOutcome(result=SUCCESS, status_text=["update"])
        return self.runStep()

    def test_mode_incremental(self):
        self.setupStep(
            cvs.CVS(cvsroot=":pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot",
                    cvsmodule="mozilla/browser/", mode='incremental',
                    login=True))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['cvs', '--version'])
            + 0,
            ExpectLogged('stat', dict(file='wkdir/CVS',
                                      logEnviron=True))
            + 0,            
            ExpectShell(workdir='wkdir',
                        command=['cvs', '-z3', 'update', '-dP'])
            + 0,
            )

        self.expectOutcome(result=SUCCESS, status_text=["update"])
        return self.runStep()

    def test_mode_incremental_not_loggedin(self):
        self.setupStep(
            cvs.CVS(cvsroot=":pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot",
                    cvsmodule="mozilla/browser/", mode='incremental',
                    login=False))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['cvs', '--version'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['cvs', '-d',
                                 ':pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot',
                                 'login'])
            + 0,
            ExpectLogged('stat', dict(file='wkdir/CVS',
                                      logEnviron=True))
            + 0,            
            ExpectShell(workdir='wkdir',
                        command=['cvs', '-z3', 'update', '-dP'])
            + 0,
            )

        self.expectOutcome(result=SUCCESS, status_text=["update"])
        return self.runStep()


    def test_mode_incremental_no_existing_repo(self):
        self.setupStep(
            cvs.CVS(cvsroot=":pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot",
                    cvsmodule="mozilla/browser/", mode='incremental',
                    login=True))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['cvs', '--version'])
            + 0,
            ExpectLogged('stat', dict(file='wkdir/CVS',
                                      logEnviron=True))
            + 1,
            ExpectShell(workdir='',
                        command=['cvs',
                                 '-d',
                                 ':pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot',
                                 '-z3', 'checkout', '-d', 'wkdir', 'mozilla/browser/'])
            + 0,
            )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        return self.runStep()


    def test_mode_full_clean_no_existing_repo(self):
        self.setupStep(
            cvs.CVS(cvsroot=":pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot",
                    cvsmodule="mozilla/browser/", mode='full', method='clean',
                    login=True))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['cvs', '--version'])
            + 0,
            ExpectLogged('stat', dict(file='wkdir/CVS',
                                      logEnviron=True))
            + 1,
            ExpectShell(workdir='',
                        command=['cvs',
                                 '-d',
                                 ':pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot',
                                 '-z3', 'checkout', '-d', 'wkdir', 'mozilla/browser/'])
            + 0,
            )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        return self.runStep()

    def test_mode_full_no_method(self):
        self.setupStep(
            cvs.CVS(cvsroot=":pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot",
                    cvsmodule="mozilla/browser/", mode='full',
                    login=True))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['cvs', '--version'])
            + 0,
            ExpectLogged('stat', dict(file='wkdir/CVS',
                                      logEnviron=True))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['cvsdiscard', '--ignore'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['cvs', '-z3', 'update', '-dP'])
            + 0,
            )

        self.expectOutcome(result=SUCCESS, status_text=["update"])
        return self.runStep()

    def test_mode_incremental_with_options(self):
        self.setupStep(
            cvs.CVS(cvsroot=":pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot",
                    cvsmodule="mozilla/browser/", mode='incremental',
                    login=True, global_options=['-q'], extra_options=['-l']))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['cvs', '--version'])
            + 0,
            ExpectLogged('stat', dict(file='wkdir/CVS',
                                      logEnviron=True))
            + 1,
            ExpectShell(workdir='',
                        command=['cvs', '-q', '-d',
                                 ':pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot',
                                 '-z3', 'checkout', '-d', 'wkdir', 'mozilla/browser/', '-l'])
            + 0,
            )
        self.expectOutcome(result=SUCCESS, status_text=["update"])
        return self.runStep()

    def test_mode_incremental_with_env_logEnviron(self):
        self.setupStep(
            cvs.CVS(cvsroot=":pserver:anonymous@cvs-mirror.mozilla.org:/cvsroot",
                    cvsmodule="mozilla/browser/", mode='incremental',
                    login=True, env={'abc': '123'}, logEnviron=False))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['cvs', '--version'],
                        env={'abc': '123'},
                        logEnviron=False)
            + 0,
            ExpectLogged('stat', dict(file='wkdir/CVS',
                                      logEnviron=False))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['cvs', '-z3', 'update', '-dP'],
                                                env={'abc': '123'},
                        logEnviron=False)
            + 0,
            )

        self.expectOutcome(result=SUCCESS, status_text=["update"])
        return self.runStep()
