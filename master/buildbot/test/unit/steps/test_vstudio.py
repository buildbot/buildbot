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

from twisted.internet import defer
from twisted.trial import unittest

from buildbot import config
from buildbot.process import results
from buildbot.process.properties import Property
from buildbot.process.results import FAILURE
from buildbot.process.results import SKIPPED
from buildbot.process.results import SUCCESS
from buildbot.process.results import WARNINGS
from buildbot.steps import vstudio
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.steps import ExpectShell
from buildbot.test.steps import TestBuildStepMixin

real_log = r"""
1>------ Build started: Project: lib1, Configuration: debug Win32 ------
1>Compiling...
1>SystemLog.cpp
1>c:\absolute\path\to\systemlog.cpp(7) : warning C4100: 'op' : unreferenced formal parameter
1>c:\absolute\path\to\systemlog.cpp(12) : warning C4100: 'statusword' : unreferenced formal parameter
1>c:\absolute\path\to\systemlog.cpp(12) : warning C4100: 'op' : unreferenced formal parameter
1>c:\absolute\path\to\systemlog.cpp(17) : warning C4100: 'retryCounter' : unreferenced formal parameter
1>c:\absolute\path\to\systemlog.cpp(17) : warning C4100: 'op' : unreferenced formal parameter
1>c:\absolute\path\to\systemlog.cpp(22) : warning C4100: 'op' : unreferenced formal parameter
1>Creating library...
1>Build log was saved at "file://c:\another\absolute\path\to\debug\BuildLog.htm"
1>lib1 - 0 error(s), 6 warning(s)
2>------ Build started: Project: product, Configuration: debug Win32 ------
2>Linking...
2>LINK : fatal error LNK1168: cannot open ../../debug/directory/dllname.dll for writing
2>Build log was saved at "file://c:\another\similar\path\to\debug\BuildLog.htm"
2>product - 1 error(s), 0 warning(s)
========== Build: 1 succeeded, 1 failed, 6 up-to-date, 0 skipped ==========
"""  # noqa pylint: disable=line-too-long


class TestAddEnvPath(unittest.TestCase):

    def do_test(self, initial_env, name, value, expected_env):
        step = vstudio.VisualStudio()
        step.env = initial_env
        step.add_env_path(name, value)
        self.assertEqual(step.env, expected_env)

    def test_new(self):
        self.do_test({}, 'PATH', r'C:\NOTHING',
                     {'PATH': r'C:\NOTHING;'})

    def test_new_semi(self):
        self.do_test({}, 'PATH', r'C:\NOTHING;',
                     {'PATH': r'C:\NOTHING;'})

    def test_existing(self):
        self.do_test({'PATH': '/bin'}, 'PATH', r'C:\NOTHING',
                     {'PATH': r'/bin;C:\NOTHING;'})

    def test_existing_semi(self):
        self.do_test({'PATH': '/bin;'}, 'PATH', r'C:\NOTHING',
                     {'PATH': r'/bin;C:\NOTHING;'})

    def test_existing_both_semi(self):
        self.do_test({'PATH': '/bin;'}, 'PATH', r'C:\NOTHING;',
                     {'PATH': r'/bin;C:\NOTHING;'})


class MSLogLineObserver(unittest.TestCase):

    def setUp(self):
        self.warnings = []
        lw = Mock()
        lw.addStdout = lambda l: self.warnings.append(l.rstrip())

        self.errors = []
        self.errors_stderr = []
        le = Mock()
        le.addStdout = lambda l: self.errors.append(('o', l.rstrip()))
        le.addStderr = lambda l: self.errors.append(('e', l.rstrip()))

        self.llo = vstudio.MSLogLineObserver(lw, le)

        self.progress = {}
        self.llo.step = Mock()
        self.llo.step.setProgress = self.progress.__setitem__

    def receiveLines(self, *lines):
        for line in lines:
            self.llo.outLineReceived(line)

    def assertResult(self, nbFiles=0, nbProjects=0, nbWarnings=0, nbErrors=0,
                     errors=None, warnings=None, progress=None):
        if errors is None:
            errors = []
        if warnings is None:
            warnings = []
        if progress is None:
            progress = {}
        self.assertEqual(
            dict(nbFiles=self.llo.nbFiles, nbProjects=self.llo.nbProjects,
                 nbWarnings=self.llo.nbWarnings,
                 nbErrors=self.llo.nbErrors, errors=self.errors,
                 warnings=self.warnings, progress=self.progress),
            dict(nbFiles=nbFiles, nbProjects=nbProjects, nbWarnings=nbWarnings,
                 nbErrors=nbErrors, errors=errors,
                 warnings=warnings, progress=progress))

    def test_outLineReceived_empty(self):
        self.llo.outLineReceived('abcd\r\n')
        self.assertResult()

    def test_outLineReceived_projects(self):
        lines = [
            "123>----- some project 1 -----",
            "123>----- some project 2 -----",
        ]
        self.receiveLines(*lines)
        self.assertResult(nbProjects=2, progress=dict(projects=2),
                          errors=[('o', l) for l in lines],
                          warnings=lines)

    def test_outLineReceived_files(self):
        lines = [
            "123>SomeClass.cpp",
            "123>SomeStuff.c",
            "123>SomeStuff.h",  # .h files not recognized
        ]
        self.receiveLines(*lines)
        self.assertResult(nbFiles=2, progress=dict(files=2))

    def test_outLineReceived_warnings(self):
        lines = [
            "abc: warning ABC123: xyz!",
            "def : warning DEF456: wxy!",
        ]
        self.receiveLines(*lines)
        self.assertResult(nbWarnings=2, progress=dict(warnings=2),
                          warnings=lines)

    def test_outLineReceived_errors(self):
        lines = [
            "error ABC123: foo",
            " error DEF456 : bar",
            " error : bar",
            " error: bar",  # NOTE: not matched
        ]
        self.receiveLines(*lines)
        self.assertResult(nbErrors=3,  # note: no progress
                          errors=[
                              ('e', "error ABC123: foo"),
                              ('e', " error DEF456 : bar"),
                              ('e', " error : bar"),
                          ])

    def test_outLineReceived_real(self):
        # based on a real logfile donated by Ben Allard
        lines = real_log.split("\n")
        self.receiveLines(*lines)
        errors = [
            ('o',
             '1>------ Build started: Project: lib1, Configuration: debug Win32 ------'),
            ('o',
             '2>------ Build started: Project: product, Configuration: debug Win32 ------'),
            ('e',
             '2>LINK : fatal error LNK1168: cannot open ../../debug/directory/dllname.dll for writing')  # noqa pylint: disable=line-too-long
        ]
        warnings = [
            '1>------ Build started: Project: lib1, Configuration: debug Win32 ------',
            "1>c:\\absolute\\path\\to\\systemlog.cpp(7) : warning C4100: 'op' : unreferenced formal parameter",  # noqa pylint: disable=line-too-long
            "1>c:\\absolute\\path\\to\\systemlog.cpp(12) : warning C4100: 'statusword' : unreferenced formal parameter",  # noqa pylint: disable=line-too-long
            "1>c:\\absolute\\path\\to\\systemlog.cpp(12) : warning C4100: 'op' : unreferenced formal parameter",  # noqa pylint: disable=line-too-long
            "1>c:\\absolute\\path\\to\\systemlog.cpp(17) : warning C4100: 'retryCounter' : unreferenced formal parameter",  # noqa pylint: disable=line-too-long
            "1>c:\\absolute\\path\\to\\systemlog.cpp(17) : warning C4100: 'op' : unreferenced formal parameter",  # noqa pylint: disable=line-too-long
            "1>c:\\absolute\\path\\to\\systemlog.cpp(22) : warning C4100: 'op' : unreferenced formal parameter",  # noqa pylint: disable=line-too-long
            '2>------ Build started: Project: product, Configuration: debug Win32 ------',
        ]
        self.assertResult(nbFiles=1, nbErrors=1, nbProjects=2, nbWarnings=6,
                          progress={'files': 1, 'projects': 2, 'warnings': 6},
                          errors=errors, warnings=warnings)


class VCx(vstudio.VisualStudio):

    def run(self):
        self.command = ["command", "here"]
        return super().run()


class VisualStudio(TestBuildStepMixin, TestReactorMixin, unittest.TestCase):

    """
    Test L{VisualStudio} with a simple subclass, L{VCx}.
    """

    def setUp(self):
        self.setup_test_reactor()
        return self.setup_test_build_step()

    def tearDown(self):
        return self.tear_down_test_build_step()

    def test_default_config(self):
        vs = vstudio.VisualStudio()
        self.assertEqual(vs.config, 'release')

    def test_simple(self):
        self.setup_step(VCx())
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['command', 'here'])
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS, state_string="compile 0 projects 0 files")
        return self.run_step()

    def test_skipped(self):
        self.setup_step(VCx(doStepIf=False))
        self.expect_commands()
        self.expect_outcome(result=SKIPPED, state_string="")
        return self.run_step()

    @defer.inlineCallbacks
    def test_installdir(self):
        self.setup_step(VCx(installdir=r'C:\I'))
        self.step.exp_installdir = r'C:\I'
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['command', 'here'])
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS, state_string="compile 0 projects 0 files")
        yield self.run_step()
        self.assertEqual(self.step.installdir, r'C:\I')

    def test_evaluate_result_failure(self):
        self.setup_step(VCx())
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['command', 'here'])
            .exit(1)
        )
        self.expect_outcome(result=FAILURE, state_string="compile 0 projects 0 files (failure)")
        return self.run_step()

    def test_evaluate_result_errors(self):
        self.setup_step(VCx())
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['command', 'here'])
            .stdout('error ABC123: foo\r\n')
            .exit(0)
        )
        self.expect_outcome(result=FAILURE,
                            state_string="compile 0 projects 0 files 1 errors (failure)")
        return self.run_step()

    def test_evaluate_result_warnings(self):
        self.setup_step(VCx())
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['command', 'here'])
            .stdout('foo: warning ABC123: foo\r\n')
            .exit(0)
        )
        self.expect_outcome(result=WARNINGS,
                            state_string="compile 0 projects 0 files 1 warnings (warnings)")
        return self.run_step()

    def test_env_setup(self):
        self.setup_step(VCx(
            INCLUDE=[r'c:\INC1', r'c:\INC2'],
            LIB=[r'c:\LIB1', r'C:\LIB2'],
            PATH=[r'c:\P1', r'C:\P2']))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['command', 'here'],
                        env=dict(
                            INCLUDE=r'c:\INC1;c:\INC2;',
                            LIB=r'c:\LIB1;C:\LIB2;',
                            PATH=r'c:\P1;C:\P2;'))
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS, state_string="compile 0 projects 0 files")
        return self.run_step()

    def test_env_setup_existing(self):
        self.setup_step(VCx(
            INCLUDE=[r'c:\INC1', r'c:\INC2'],
            LIB=[r'c:\LIB1', r'C:\LIB2'],
            PATH=[r'c:\P1', r'C:\P2']))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['command', 'here'],
                        env=dict(
                            INCLUDE=r'c:\INC1;c:\INC2;',
                            LIB=r'c:\LIB1;C:\LIB2;',
                            PATH=r'c:\P1;C:\P2;'))
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS, state_string="compile 0 projects 0 files")
        return self.run_step()

    @defer.inlineCallbacks
    def test_rendering(self):
        self.setup_step(VCx(
            projectfile=Property('a'),
            config=Property('b'),
            project=Property('c')))
        self.properties.setProperty('a', 'aa', 'Test')
        self.properties.setProperty('b', 'bb', 'Test')
        self.properties.setProperty('c', 'cc', 'Test')
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['command', 'here'])
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS, state_string="compile 0 projects 0 files")
        yield self.run_step()

        self.assertEqual(
                [self.step.projectfile, self.step.config, self.step.project],
                ['aa', 'bb', 'cc'])


class TestVC6(TestBuildStepMixin, TestReactorMixin, unittest.TestCase):

    def setUp(self):
        self.setup_test_reactor()
        return self.setup_test_build_step()

    def tearDown(self):
        return self.tear_down_test_build_step()

    def getExpectedEnv(self, installdir, LIB=None, p=None, i=None):
        include = [
            installdir + r'\VC98\INCLUDE;',
            installdir + r'\VC98\ATL\INCLUDE;',
            installdir + r'\VC98\MFC\INCLUDE;',
        ]
        lib = [
            installdir + r'\VC98\LIB;',
            installdir + r'\VC98\MFC\LIB;',
        ]
        path = [
            installdir + r'\Common\msdev98\BIN;',
            installdir + r'\VC98\BIN;',
            installdir + r'\Common\TOOLS\WINNT;',
            installdir + r'\Common\TOOLS;',
        ]
        if p:
            path.insert(0, f'{p};')
        if i:
            include.insert(0, f'{i};')
        if LIB:
            lib.insert(0, f'{LIB};')
        return dict(
            INCLUDE=''.join(include),
            LIB=''.join(lib),
            PATH=''.join(path),
        )

    def test_args(self):
        self.setup_step(vstudio.VC6(projectfile='pf', config='cfg',
                                   project='pj'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['msdev', 'pf', '/MAKE',
                                 'pj - cfg', '/REBUILD'],
                        env=self.getExpectedEnv(
                            r'C:\Program Files\Microsoft Visual Studio'))
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS, state_string="compile 0 projects 0 files")
        return self.run_step()

    def test_clean(self):
        self.setup_step(vstudio.VC6(projectfile='pf', config='cfg',
                                   project='pj', mode='clean'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['msdev', 'pf', '/MAKE',
                                 'pj - cfg', '/CLEAN'],
                        env=self.getExpectedEnv(
                            r'C:\Program Files\Microsoft Visual Studio'))
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS, state_string="compile 0 projects 0 files")
        return self.run_step()

    def test_noproj_build(self):
        self.setup_step(vstudio.VC6(projectfile='pf', config='cfg',
                                   mode='build'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['msdev', 'pf', '/MAKE',
                                 'ALL - cfg', '/BUILD'],
                        env=self.getExpectedEnv(
                            r'C:\Program Files\Microsoft Visual Studio'))
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS, state_string="compile 0 projects 0 files")
        return self.run_step()

    def test_env_prepend(self):
        self.setup_step(vstudio.VC6(projectfile='pf', config='cfg',
                                   project='pj', PATH=['p'], INCLUDE=['i'],
                                   LIB=['l']))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['msdev', 'pf', '/MAKE',
                                 'pj - cfg', '/REBUILD',
                                 '/USEENV'],  # note extra param
                        env=self.getExpectedEnv(
                            r'C:\Program Files\Microsoft Visual Studio',
                            LIB='l', p='p', i='i'))
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS, state_string="compile 0 projects 0 files")
        return self.run_step()


class TestVC7(TestBuildStepMixin, TestReactorMixin, unittest.TestCase):

    def setUp(self):
        self.setup_test_reactor()
        return self.setup_test_build_step()

    def tearDown(self):
        return self.tear_down_test_build_step()

    def getExpectedEnv(self, installdir, LIB=None, p=None, i=None):
        include = [
            installdir + r'\VC7\INCLUDE;',
            installdir + r'\VC7\ATLMFC\INCLUDE;',
            installdir + r'\VC7\PlatformSDK\include;',
            installdir + r'\SDK\v1.1\include;',
        ]
        lib = [
            installdir + r'\VC7\LIB;',
            installdir + r'\VC7\ATLMFC\LIB;',
            installdir + r'\VC7\PlatformSDK\lib;',
            installdir + r'\SDK\v1.1\lib;',
        ]
        path = [
            installdir + r'\Common7\IDE;',
            installdir + r'\VC7\BIN;',
            installdir + r'\Common7\Tools;',
            installdir + r'\Common7\Tools\bin;',
        ]
        if p:
            path.insert(0, f'{p};')
        if i:
            include.insert(0, f'{i};')
        if LIB:
            lib.insert(0, f'{LIB};')
        return dict(
            INCLUDE=''.join(include),
            LIB=''.join(lib),
            PATH=''.join(path),
        )

    def test_args(self):
        self.setup_step(vstudio.VC7(projectfile='pf', config='cfg',
                                   project='pj'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['devenv.com', 'pf', '/Rebuild', 'cfg',
                                 '/Project', 'pj'],
                        env=self.getExpectedEnv(
                            r'C:\Program Files\Microsoft Visual Studio .NET 2003'))
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS, state_string="compile 0 projects 0 files")
        return self.run_step()

    def test_clean(self):
        self.setup_step(vstudio.VC7(projectfile='pf', config='cfg',
                                   project='pj', mode='clean'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['devenv.com', 'pf', '/Clean', 'cfg',
                                 '/Project', 'pj'],
                        env=self.getExpectedEnv(
                            r'C:\Program Files\Microsoft Visual Studio .NET 2003'))
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS, state_string="compile 0 projects 0 files")
        return self.run_step()

    def test_noproj_build(self):
        self.setup_step(vstudio.VC7(projectfile='pf', config='cfg',
                                   mode='build'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['devenv.com', 'pf', '/Build', 'cfg'],
                        env=self.getExpectedEnv(
                            r'C:\Program Files\Microsoft Visual Studio .NET 2003'))
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS, state_string="compile 0 projects 0 files")
        return self.run_step()

    def test_env_prepend(self):
        self.setup_step(vstudio.VC7(projectfile='pf', config='cfg',
                                   project='pj', PATH=['p'], INCLUDE=['i'],
                                   LIB=['l']))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['devenv.com', 'pf', '/Rebuild', 'cfg',
                                 '/UseEnv', '/Project', 'pj'],
                        env=self.getExpectedEnv(
                            r'C:\Program Files\Microsoft Visual Studio .NET 2003',
                            LIB='l', p='p', i='i'))
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS, state_string="compile 0 projects 0 files")
        return self.run_step()


class VC8ExpectedEnvMixin:
    # used for VC8 and VC9Express

    def getExpectedEnv(self, installdir, x64=False, LIB=None, i=None, p=None):
        include = [
            installdir + r'\VC\INCLUDE;',
            installdir + r'\VC\ATLMFC\include;',
            installdir + r'\VC\PlatformSDK\include;',
        ]
        lib = [
            installdir + r'\VC\LIB;',
            installdir + r'\VC\ATLMFC\LIB;',
            installdir + r'\VC\PlatformSDK\lib;',
            installdir + r'\SDK\v2.0\lib;',
        ]
        path = [
            installdir + r'\Common7\IDE;',
            installdir + r'\VC\BIN;',
            installdir + r'\Common7\Tools;',
            installdir + r'\Common7\Tools\bin;',
            installdir + r'\VC\PlatformSDK\bin;',
            installdir + r'\SDK\v2.0\bin;',
            installdir + r'\VC\VCPackages;',
            r'${PATH};',
        ]
        if x64:
            path.insert(1, installdir + r'\VC\BIN\x86_amd64;')
            lib = [lb[:-1] + r'\amd64;' for lb in lib]
        if LIB:
            lib.insert(0, f'{LIB};')
        if p:
            path.insert(0, f'{p};')
        if i:
            include.insert(0, f'{i};')
        return dict(
            INCLUDE=''.join(include),
            LIB=''.join(lib),
            PATH=''.join(path),
        )


class TestVC8(VC8ExpectedEnvMixin, TestBuildStepMixin, TestReactorMixin,
              unittest.TestCase):

    def setUp(self):
        self.setup_test_reactor()
        return self.setup_test_build_step()

    def tearDown(self):
        return self.tear_down_test_build_step()

    def test_args(self):
        self.setup_step(vstudio.VC8(projectfile='pf', config='cfg',
                                   project='pj', arch='arch'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['devenv.com', 'pf', '/Rebuild',
                                 'cfg', '/Project', 'pj'],
                        env=self.getExpectedEnv(
                            r'C:\Program Files\Microsoft Visual Studio 8'))
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS, state_string="compile 0 projects 0 files")
        return self.run_step()

    def test_args_x64(self):
        self.setup_step(vstudio.VC8(projectfile='pf', config='cfg',
                                   project='pj', arch='x64'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['devenv.com', 'pf', '/Rebuild',
                                 'cfg', '/Project', 'pj'],
                        env=self.getExpectedEnv(
                            r'C:\Program Files\Microsoft Visual Studio 8',
                            x64=True))
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS, state_string="compile 0 projects 0 files")
        return self.run_step()

    def test_clean(self):
        self.setup_step(vstudio.VC8(projectfile='pf', config='cfg',
                                   project='pj', mode='clean'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['devenv.com', 'pf', '/Clean',
                                 'cfg', '/Project', 'pj'],
                        env=self.getExpectedEnv(
                            r'C:\Program Files\Microsoft Visual Studio 8'))
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS, state_string="compile 0 projects 0 files")
        return self.run_step()

    @defer.inlineCallbacks
    def test_rendering(self):
        self.setup_step(vstudio.VC8(projectfile='pf', config='cfg',
                                   arch=Property('a')))
        self.properties.setProperty('a', 'x64', 'Test')
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['devenv.com', 'pf', '/Rebuild', 'cfg'],
                        env=self.getExpectedEnv(
                            r'C:\Program Files\Microsoft Visual Studio 8',
                            x64=True))  # property has expected effect
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS, state_string="compile 0 projects 0 files")
        yield self.run_step()

        self.assertEqual(self.step.arch, 'x64')


class TestVCExpress9(VC8ExpectedEnvMixin, TestBuildStepMixin,
                     TestReactorMixin,
                     unittest.TestCase):

    def setUp(self):
        self.setup_test_reactor()
        return self.setup_test_build_step()

    def tearDown(self):
        return self.tear_down_test_build_step()

    def test_args(self):
        self.setup_step(vstudio.VCExpress9(projectfile='pf', config='cfg',
                                          project='pj'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['vcexpress', 'pf', '/Rebuild',
                                 'cfg', '/Project', 'pj'],
                        env=self.getExpectedEnv(
                            # note: still uses version 8 (?!)
                            r'C:\Program Files\Microsoft Visual Studio 8'))
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS, state_string="compile 0 projects 0 files")
        return self.run_step()

    def test_clean(self):
        self.setup_step(vstudio.VCExpress9(projectfile='pf', config='cfg',
                                          project='pj', mode='clean'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['vcexpress', 'pf', '/Clean',
                                 'cfg', '/Project', 'pj'],
                        env=self.getExpectedEnv(
                            # note: still uses version 8 (?!)
                            r'C:\Program Files\Microsoft Visual Studio 8'))
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS, state_string="compile 0 projects 0 files")
        return self.run_step()

    def test_mode_build_env(self):
        self.setup_step(vstudio.VCExpress9(projectfile='pf', config='cfg',
                                          project='pj', mode='build', INCLUDE=['i']))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['vcexpress', 'pf', '/Build',
                                 'cfg', '/UseEnv', '/Project', 'pj'],
                        env=self.getExpectedEnv(
                            r'C:\Program Files\Microsoft Visual Studio 8',
                            i='i'))
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS, state_string="compile 0 projects 0 files")
        return self.run_step()


class TestVC9(VC8ExpectedEnvMixin, TestBuildStepMixin, TestReactorMixin,
              unittest.TestCase):

    def setUp(self):
        self.setup_test_reactor()
        return self.setup_test_build_step()

    def tearDown(self):
        return self.tear_down_test_build_step()

    def test_installdir(self):
        self.setup_step(vstudio.VC9(projectfile='pf', config='cfg',
                                   project='pj'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['devenv.com', 'pf', '/Rebuild',
                                 'cfg', '/Project', 'pj'],
                        env=self.getExpectedEnv(
                            r'C:\Program Files\Microsoft Visual Studio 9.0'))
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS, state_string="compile 0 projects 0 files")
        return self.run_step()


class TestVC10(VC8ExpectedEnvMixin, TestBuildStepMixin, TestReactorMixin,
               unittest.TestCase):

    def setUp(self):
        self.setup_test_reactor()
        return self.setup_test_build_step()

    def tearDown(self):
        return self.tear_down_test_build_step()

    def test_installdir(self):
        self.setup_step(vstudio.VC10(projectfile='pf', config='cfg',
                                    project='pj'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['devenv.com', 'pf', '/Rebuild',
                                 'cfg', '/Project', 'pj'],
                        env=self.getExpectedEnv(
                            r'C:\Program Files\Microsoft Visual Studio 10.0'))
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS, state_string="compile 0 projects 0 files")
        return self.run_step()


class TestVC11(VC8ExpectedEnvMixin, TestBuildStepMixin, TestReactorMixin,
               unittest.TestCase):

    def setUp(self):
        self.setup_test_reactor()
        return self.setup_test_build_step()

    def tearDown(self):
        return self.tear_down_test_build_step()

    def test_installdir(self):
        self.setup_step(vstudio.VC11(projectfile='pf', config='cfg',
                                    project='pj'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['devenv.com', 'pf', '/Rebuild',
                                 'cfg', '/Project', 'pj'],
                        env=self.getExpectedEnv(
                            r'C:\Program Files\Microsoft Visual Studio 11.0'))
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS, state_string="compile 0 projects 0 files")
        return self.run_step()


class TestMsBuild(TestBuildStepMixin, TestReactorMixin, unittest.TestCase):

    def setUp(self):
        self.setup_test_reactor()
        return self.setup_test_build_step()

    def tearDown(self):
        return self.tear_down_test_build_step()

    @defer.inlineCallbacks
    def test_no_platform(self):
        self.setup_step(vstudio.MsBuild(
                            projectfile='pf', config='cfg', platform=None, project='pj'))

        self.expect_outcome(result=results.EXCEPTION, state_string="built pj for cfg|None")
        yield self.run_step()
        self.assertEqual(len(self.flushLoggedErrors(config.ConfigErrors)), 1)

    def test_rebuild_project(self):
        self.setup_step(vstudio.MsBuild(
            projectfile='pf', config='cfg', platform='Win32', project='pj'))

        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command='"%VCENV_BAT%" x86 && msbuild "pf" /p:Configuration="cfg" /p:Platform="Win32" /maxcpucount /t:"pj"',  # noqa pylint: disable=line-too-long
                        env={'VCENV_BAT': r'${VS110COMNTOOLS}..\..\VC\vcvarsall.bat'})
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS, state_string="built pj for cfg|Win32")
        return self.run_step()

    def test_build_project(self):
        self.setup_step(vstudio.MsBuild(
            projectfile='pf', config='cfg', platform='Win32', project='pj', mode='build'))

        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command='"%VCENV_BAT%" x86 && msbuild "pf" /p:Configuration="cfg" /p:Platform="Win32" /maxcpucount /t:"pj:Build"',  # noqa pylint: disable=line-too-long
                        env={'VCENV_BAT': r'${VS110COMNTOOLS}..\..\VC\vcvarsall.bat'})
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS, state_string="built pj for cfg|Win32")
        return self.run_step()

    def test_clean_project(self):
        self.setup_step(vstudio.MsBuild(
            projectfile='pf', config='cfg', platform='Win32', project='pj', mode='clean'))

        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command='"%VCENV_BAT%" x86 && msbuild "pf" /p:Configuration="cfg" /p:Platform="Win32" /maxcpucount /t:"pj:Clean"',  # noqa pylint: disable=line-too-long
                        env={'VCENV_BAT': r'${VS110COMNTOOLS}..\..\VC\vcvarsall.bat'})
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS, state_string="built pj for cfg|Win32")
        return self.run_step()

    def test_rebuild_project_with_defines(self):
        self.setup_step(vstudio.MsBuild(
            projectfile='pf', config='cfg', platform='Win32', project='pj',
            defines=['Define1', 'Define2=42']))

        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command='"%VCENV_BAT%" x86 && msbuild "pf" /p:Configuration="cfg" /p:Platform="Win32" /maxcpucount /t:"pj" /p:DefineConstants="Define1;Define2=42"',  # noqa pylint: disable=line-too-long
                        env={'VCENV_BAT': r'${VS110COMNTOOLS}..\..\VC\vcvarsall.bat'})
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS, state_string="built pj for cfg|Win32")
        return self.run_step()

    def test_rebuild_solution(self):
        self.setup_step(
            vstudio.MsBuild(projectfile='pf', config='cfg', platform='x64'))

        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command='"%VCENV_BAT%" x86 && msbuild "pf" /p:Configuration="cfg" /p:Platform="x64" /maxcpucount /t:Rebuild',  # noqa pylint: disable=line-too-long
                        env={'VCENV_BAT': r'${VS110COMNTOOLS}..\..\VC\vcvarsall.bat'})
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS, state_string="built solution for cfg|x64")
        return self.run_step()


class TestMsBuild141(TestBuildStepMixin, TestReactorMixin, unittest.TestCase):

    def setUp(self):
        self.setup_test_reactor()
        return self.setup_test_build_step()

    def tearDown(self):
        return self.tear_down_test_build_step()

    @defer.inlineCallbacks
    def test_no_platform(self):
        self.setup_step(vstudio.MsBuild(
                            projectfile='pf', config='cfg', platform=None, project='pj'))

        self.expect_outcome(result=results.EXCEPTION, state_string="built pj for cfg|None")
        yield self.run_step()
        self.assertEqual(len(self.flushLoggedErrors(config.ConfigErrors)), 1)

    def test_rebuild_project(self):
        self.setup_step(vstudio.MsBuild141(
            projectfile='pf', config='cfg', platform='Win32', project='pj'))

        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command='FOR /F "tokens=*" %%I in (\'vswhere.exe -version "[15.0,16.0)" -products * -property installationPath\')  do "%%I\\%VCENV_BAT%" x86 && msbuild "pf" /p:Configuration="cfg" /p:Platform="Win32" /maxcpucount /t:"pj"',  # noqa pylint: disable=line-too-long
                        env={'VCENV_BAT': r'\VC\Auxiliary\Build\vcvarsall.bat',
                             'PATH': 'C:\\Program Files (x86)\\Microsoft Visual Studio\\Installer\\;C:\\Program Files\\Microsoft Visual Studio\\Installer\\;${PATH};'})  # noqa pylint: disable=line-too-long
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS, state_string="compile 0 projects 0 files")
        return self.run_step()

    def test_build_project(self):
        self.setup_step(vstudio.MsBuild141(
            projectfile='pf', config='cfg', platform='Win32', project='pj', mode='build'))

        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command='FOR /F "tokens=*" %%I in (\'vswhere.exe -version "[15.0,16.0)" -products * -property installationPath\')  do "%%I\\%VCENV_BAT%" x86 && msbuild "pf" /p:Configuration="cfg" /p:Platform="Win32" /maxcpucount /t:"pj:Build"',  # noqa pylint: disable=line-too-long
                        env={'VCENV_BAT': r'\VC\Auxiliary\Build\vcvarsall.bat',
                             'PATH': 'C:\\Program Files (x86)\\Microsoft Visual Studio\\Installer\\;C:\\Program Files\\Microsoft Visual Studio\\Installer\\;${PATH};'})  # noqa pylint: disable=line-too-long
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS, state_string="compile 0 projects 0 files")
        return self.run_step()

    def test_clean_project(self):
        self.setup_step(vstudio.MsBuild141(
            projectfile='pf', config='cfg', platform='Win32', project='pj', mode='clean'))

        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command='FOR /F "tokens=*" %%I in (\'vswhere.exe -version "[15.0,16.0)" -products * -property installationPath\')  do "%%I\\%VCENV_BAT%" x86 && msbuild "pf" /p:Configuration="cfg" /p:Platform="Win32" /maxcpucount /t:"pj:Clean"',  # noqa pylint: disable=line-too-long
                        env={'VCENV_BAT': r'\VC\Auxiliary\Build\vcvarsall.bat',
                             'PATH': 'C:\\Program Files (x86)\\Microsoft Visual Studio\\Installer\\;C:\\Program Files\\Microsoft Visual Studio\\Installer\\;${PATH};'})  # noqa pylint: disable=line-too-long
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS, state_string="compile 0 projects 0 files")
        return self.run_step()

    def test_rebuild_project_with_defines(self):
        self.setup_step(vstudio.MsBuild141(
            projectfile='pf', config='cfg', platform='Win32', project='pj',
            defines=['Define1', 'Define2=42']))

        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command='FOR /F "tokens=*" %%I in (\'vswhere.exe -version "[15.0,16.0)" -products * -property installationPath\')  do "%%I\\%VCENV_BAT%" x86 && msbuild "pf" /p:Configuration="cfg" /p:Platform="Win32" /maxcpucount /t:"pj" /p:DefineConstants="Define1;Define2=42"',  # noqa pylint: disable=line-too-long
                        env={'VCENV_BAT': r'\VC\Auxiliary\Build\vcvarsall.bat',
                             'PATH': 'C:\\Program Files (x86)\\Microsoft Visual Studio\\Installer\\;C:\\Program Files\\Microsoft Visual Studio\\Installer\\;${PATH};'})  # noqa pylint: disable=line-too-long
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS, state_string="compile 0 projects 0 files")
        return self.run_step()

    def test_rebuild_solution(self):
        self.setup_step(
            vstudio.MsBuild141(projectfile='pf', config='cfg', platform='x64'))

        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command='FOR /F "tokens=*" %%I in (\'vswhere.exe -version "[15.0,16.0)" -products * -property installationPath\')  do "%%I\\%VCENV_BAT%" x86 && msbuild "pf" /p:Configuration="cfg" /p:Platform="x64" /maxcpucount /t:Rebuild',  # noqa pylint: disable=line-too-long
                        env={'VCENV_BAT': r'\VC\Auxiliary\Build\vcvarsall.bat',
                             'PATH': 'C:\\Program Files (x86)\\Microsoft Visual Studio\\Installer\\;C:\\Program Files\\Microsoft Visual Studio\\Installer\\;${PATH};'})  # noqa pylint: disable=line-too-long
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS, state_string="compile 0 projects 0 files")
        return self.run_step()

    def test_aliases_MsBuild15(self):
        self.assertIdentical(vstudio.MsBuild141, vstudio.MsBuild15)


class TestMsBuild16(TestBuildStepMixin, TestReactorMixin, unittest.TestCase):

    def setUp(self):
        self.setup_test_reactor()
        return self.setup_test_build_step()

    def tearDown(self):
        return self.tear_down_test_build_step()

    def test_version_range_is_correct(self):
        self.setup_step(vstudio.MsBuild16(
            projectfile='pf', config='cfg', platform='Win32', project='pj'))

        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command='FOR /F "tokens=*" %%I in (\'vswhere.exe -version "[16.0,17.0)" -products * -property installationPath\')  do "%%I\\%VCENV_BAT%" x86 && msbuild "pf" /p:Configuration="cfg" /p:Platform="Win32" /maxcpucount /t:"pj"',  # noqa pylint: disable=line-too-long
                        env={'VCENV_BAT': r'\VC\Auxiliary\Build\vcvarsall.bat',
                             'PATH': 'C:\\Program Files (x86)\\Microsoft Visual Studio\\Installer\\;C:\\Program Files\\Microsoft Visual Studio\\Installer\\;${PATH};'})  # noqa pylint: disable=line-too-long
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS, state_string="compile 0 projects 0 files")
        return self.run_step()


class TestMsBuild17(TestBuildStepMixin, TestReactorMixin, unittest.TestCase):

    def setUp(self):
        self.setup_test_reactor()
        return self.setup_test_build_step()

    def tearDown(self):
        return self.tear_down_test_build_step()

    def test_version_range_is_correct(self):
        self.setup_step(vstudio.MsBuild17(
            projectfile='pf', config='cfg', platform='Win32', project='pj'))

        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command='FOR /F "tokens=*" %%I in (\'vswhere.exe -version "[17.0,18.0)" -products * -property installationPath\')  do "%%I\\%VCENV_BAT%" x86 && msbuild "pf" /p:Configuration="cfg" /p:Platform="Win32" /maxcpucount /t:"pj"',  # noqa pylint: disable=line-too-long
                        env={'VCENV_BAT': r'\VC\Auxiliary\Build\vcvarsall.bat',
                             'PATH': 'C:\\Program Files (x86)\\Microsoft Visual Studio\\Installer\\;C:\\Program Files\\Microsoft Visual Studio\\Installer\\;${PATH};'})  # noqa pylint: disable=line-too-long
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS, state_string="compile 0 projects 0 files")
        return self.run_step()


class Aliases(unittest.TestCase):

    def test_vs2003(self):
        self.assertIdentical(vstudio.VS2003, vstudio.VC7)

    def test_vs2005(self):
        self.assertIdentical(vstudio.VS2005, vstudio.VC8)

    def test_vs2008(self):
        self.assertIdentical(vstudio.VS2008, vstudio.VC9)

    def test_vs2010(self):
        self.assertIdentical(vstudio.VS2010, vstudio.VC10)

    def test_vs2012(self):
        self.assertIdentical(vstudio.VS2012, vstudio.VC11)
