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
# Portions Copyright 2013 Bad Dog Consulting

import platform
import textwrap

from twisted.internet import error
from twisted.python import reflect
from twisted.trial import unittest

from buildbot.process.results import RETRY
from buildbot.process.results import SUCCESS
from buildbot.steps.source.p4 import P4
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.steps import ExpectRmdir
from buildbot.test.steps import ExpectShell
from buildbot.test.util import sourcesteps
from buildbot.test.util.config import ConfigErrorsMixin
from buildbot.test.util.properties import ConstantRenderable

_is_windows = (platform.system() == 'Windows')


class TestP4(sourcesteps.SourceStepMixin, TestReactorMixin, ConfigErrorsMixin,
             unittest.TestCase):

    def setUp(self):
        self.setup_test_reactor()
        return self.setUpSourceStep()

    def tearDown(self):
        return self.tearDownSourceStep()

    def setup_step(self, step, args=None, patch=None, **kwargs):
        if args is None:
            args = {}
        step = super().setup_step(step, args={}, patch=None, **kwargs)
        self.build.getSourceStamp().revision = args.get('revision', None)

        # builddir property used to create absolute path required in perforce
        # client spec.
        workspace_dir = '/home/user/workspace'
        if _is_windows:
            workspace_dir = r'C:\Users\username\Workspace'
            self.build.path_module = reflect.namedModule("ntpath")
        self.properties.setProperty('builddir', workspace_dir, 'P4')

    def test_no_empty_step_config(self):
        with self.assertRaisesConfigError('You must provide p4base or p4viewspec'):
            P4()

    def test_p4base_has_whitespace(self):
        with self.assertRaisesConfigError(
                'p4base should not end with a trailing / [p4base = //depot with space/]'):
            P4(p4base='//depot with space/')

    def test_p4branch_has_whitespace(self):
        with self.assertRaisesConfigError(
                'p4base should not end with a trailing / [p4base = //depot/]'):
            P4(p4base='//depot/', p4branch='branch with space')

    def test_no_p4base_has_leading_slash_step_config(self):
        with self.assertRaisesConfigError('p4base should start with // [p4base = depot/]'):
            P4(p4base='depot/')

    def test_no_multiple_type_step_config(self):
        with self.assertRaisesConfigError(
                'Either provide p4viewspec or p4base and p4branch (and optionally p4extra_views)'):
            P4(p4viewspec=('//depot/trunk', ''), p4base='//depot',
               p4branch='trunk', p4extra_views=['src', 'doc'])

    def test_no_p4viewspec_is_string_step_config(self):
        with self.assertRaisesConfigError(
                'p4viewspec must not be a string, and should be a sequence of 2 element sequences'):
            P4(p4viewspec='a_bad_idea')

    def test_no_p4base_has_trailing_slash_step_config(self):
        with self.assertRaisesConfigError(
                'p4base should not end with a trailing / [p4base = //depot/]'):
            P4(p4base='//depot/')

    def test_no_p4branch_has_trailing_slash_step_config(self):
        with self.assertRaisesConfigError(
                'p4branch should not end with a trailing / [p4branch = blah/]'):
            P4(p4base='//depot', p4branch='blah/')

    def test_no_p4branch_with_no_p4base_step_config(self):
        with self.assertRaisesConfigError('You must provide p4base or p4viewspec'):
            P4(p4branch='blah')

    def test_no_p4extra_views_with_no_p4base_step_config(self):
        with self.assertRaisesConfigError('You must provide p4base or p4viewspec'):
            P4(p4extra_views='blah')

    def test_incorrect_mode(self):
        with self.assertRaisesConfigError(
                "mode invalid is not an IRenderable, or one of ('incremental', 'full')"):
            P4(p4base='//depot', mode='invalid')

    def test_mode_incremental_p4base_with_revision(self):
        self.setup_step(P4(p4port='localhost:12000', mode='incremental',
                          p4base='//depot', p4branch='trunk',
                          p4user='user', p4client='p4_client1', p4passwd='pass'),
                       dict(revision='100',))

        root_dir = '/home/user/workspace/wkdir'
        if _is_windows:
            root_dir = r'C:\Users\username\Workspace\wkdir'
        client_spec = textwrap.dedent(f'''\
        Client: p4_client1

        Owner: user

        Description:
        \tCreated by user

        Root:\t{root_dir}

        Options:\tallwrite rmdir

        LineEnd:\tlocal

        View:
        \t//depot/trunk/... //p4_client1/...
        ''')

        self.expect_commands(
            ExpectShell(workdir='wkdir',  # defaults to this, only changes if it has a copy mode.
                        command=['p4', '-V'])  # expected remote command
            .exit(0),  # expected exit status

            ExpectShell(workdir='wkdir',
                        command=['p4', '-p', 'localhost:12000', '-u', 'user',
                                 '-P', ('obfuscated', 'pass', 'XXXXXX'),
                                 '-c', 'p4_client1', 'client', '-i'],
                        initial_stdin=client_spec)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['p4', '-p', 'localhost:12000', '-u', 'user',
                                 '-P', ('obfuscated', 'pass', 'XXXXXX'),
                                 '-c', 'p4_client1', 'sync', '//depot...@100'])
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['p4', '-p', 'localhost:12000', '-u', 'user',
                                 '-P', ('obfuscated', 'pass', 'XXXXXX'),
                                 '-c', 'p4_client1', 'changes', '-m1', '#have'])
            .stdout("Change 100 on 2013/03/21 by user@machine \'duh\'")
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property('got_revision', '100', 'P4')
        return self.run_step()

    def _incremental(self, client_stdin='', extra_args=None, workdir='wkdir', timeout=20 * 60):
        if extra_args is None:
            extra_args = []

        self.expect_commands(
            ExpectShell(workdir=workdir,
                        command=['p4', '-V'])  # expected remote command
            .exit(0),  # expected exit status

            ExpectShell(workdir=workdir,
                        timeout=timeout,
                        command=['p4', '-p', 'localhost:12000', '-u', 'user',
                                 '-P', ('obfuscated', 'pass', 'XXXXXX'),
                                 '-c', 'p4_client1', 'client', '-i'],
                        initial_stdin=client_stdin,)
            .exit(0),
            ExpectShell(workdir=workdir,
                        timeout=timeout,
                        command=(['p4', '-p', 'localhost:12000', '-u', 'user',
                                  '-P', ('obfuscated', 'pass', 'XXXXXX'), '-c', 'p4_client1']
                                 + extra_args + ['sync']))
            .exit(0),
            ExpectShell(workdir=workdir,
                        timeout=timeout,
                        command=['p4', '-p', 'localhost:12000', '-u', 'user',
                                 '-P', ('obfuscated', 'pass', 'XXXXXX'),
                                 '-c', 'p4_client1', 'changes', '-m1', '#have'])
            .stdout("Change 100 on 2013/03/21 by user@machine \'duh\'")
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property('got_revision', '100', 'P4')
        return self.run_step()

    def test_mode_incremental_p4base(self):
        self.setup_step(P4(p4port='localhost:12000', mode='incremental',
                          p4base='//depot', p4branch='trunk',
                          p4user='user', p4client='p4_client1', p4passwd='pass'))

        root_dir = '/home/user/workspace/wkdir'
        if _is_windows:
            root_dir = r'C:\Users\username\Workspace\wkdir'
        client_spec = textwrap.dedent(f'''\
        Client: p4_client1

        Owner: user

        Description:
        \tCreated by user

        Root:\t{root_dir}

        Options:\tallwrite rmdir

        LineEnd:\tlocal

        View:
        \t//depot/trunk/... //p4_client1/...
        ''')
        self._incremental(client_stdin=client_spec)

    def test_mode_incremental_p4base_with_no_branch(self):
        self.setup_step(P4(p4port='localhost:12000', mode='incremental',
                          p4base='//depot/trunk',
                          p4user='user', p4client='p4_client1', p4passwd='pass'))

        root_dir = '/home/user/workspace/wkdir'
        if _is_windows:
            root_dir = r'C:\Users\username\Workspace\wkdir'
        client_spec = textwrap.dedent(f'''\
        Client: p4_client1

        Owner: user

        Description:
        \tCreated by user

        Root:\t{root_dir}

        Options:\tallwrite rmdir

        LineEnd:\tlocal

        View:
        \t//depot/trunk/... //p4_client1/...
        ''')
        self._incremental(client_stdin=client_spec)

    def test_mode_incremental_p4base_with_p4extra_views(self):
        self.setup_step(P4(p4port='localhost:12000', mode='incremental',
                          p4base='//depot', p4branch='trunk',
                          p4extra_views=[('-//depot/trunk/test', 'test'),
                                         ('-//depot/trunk/doc', 'doc'),
                                         ('-//depot/trunk/white space', 'white space')],
                          p4user='user', p4client='p4_client1', p4passwd='pass'))

        root_dir = '/home/user/workspace/wkdir'
        if _is_windows:
            root_dir = r'C:\Users\username\Workspace\wkdir'
        client_spec = textwrap.dedent(f'''\
        Client: p4_client1

        Owner: user

        Description:
        \tCreated by user

        Root:\t{root_dir}

        Options:\tallwrite rmdir

        LineEnd:\tlocal

        View:
        \t//depot/trunk/... //p4_client1/...
        \t-//depot/trunk/test/... //p4_client1/test/...
        \t-//depot/trunk/doc/... //p4_client1/doc/...
        \t"-//depot/trunk/white space/..." "//p4_client1/white space/..."
        ''')
        self._incremental(client_stdin=client_spec)

    def test_mode_incremental_p4viewspec(self):
        self.setup_step(P4(p4port='localhost:12000', mode='incremental',
                          p4viewspec=[('//depot/trunk/', ''),
                                      ('//depot/white space/', 'white space/'),
                                      ('-//depot/white space/excluded/', 'white space/excluded/')],
                          p4user='user', p4client='p4_client1', p4passwd='pass'))

        root_dir = '/home/user/workspace/wkdir'
        if _is_windows:
            root_dir = r'C:\Users\username\Workspace\wkdir'
        client_spec = textwrap.dedent(f'''\
        Client: p4_client1

        Owner: user

        Description:
        \tCreated by user

        Root:\t{root_dir}

        Options:\tallwrite rmdir

        LineEnd:\tlocal

        View:
        \t//depot/trunk/... //p4_client1/...
        \t"//depot/white space/..." "//p4_client1/white space/..."
        \t"-//depot/white space/excluded/..." "//p4_client1/white space/excluded/..."
        ''')
        self._incremental(client_stdin=client_spec)

    def test_mode_incremental_p4viewspec_suffix(self):
        self.setup_step(P4(p4port='localhost:12000', mode='incremental',
                          p4viewspec_suffix=None,
                          p4viewspec=[('//depot/trunk/foo.xml', 'bar.xml'),
                                      ('//depot/white space/...',
                                       'white space/...'),
                                      ('-//depot/white space/excluded/...',
                                       'white space/excluded/...')],
                          p4user='user', p4client='p4_client1', p4passwd='pass'))

        root_dir = '/home/user/workspace/wkdir'
        if _is_windows:
            root_dir = r'C:\Users\username\Workspace\wkdir'
        client_spec = textwrap.dedent(f'''\
        Client: p4_client1

        Owner: user

        Description:
        \tCreated by user

        Root:\t{root_dir}

        Options:\tallwrite rmdir

        LineEnd:\tlocal

        View:
        \t//depot/trunk/foo.xml //p4_client1/bar.xml
        \t"//depot/white space/..." "//p4_client1/white space/..."
        \t"-//depot/white space/excluded/..." "//p4_client1/white space/excluded/..."
        ''')
        self._incremental(client_stdin=client_spec)

    def test_mode_incremental_p4client_spec_options(self):
        self.setup_step(P4(p4port='localhost:12000', mode='incremental',
                          p4base='//depot', p4branch='trunk',
                          p4client_spec_options='rmdir compress',
                          p4user='user', p4client='p4_client1', p4passwd='pass'))

        root_dir = '/home/user/workspace/wkdir'
        if _is_windows:
            root_dir = r'C:\Users\username\Workspace\wkdir'
        client_spec = textwrap.dedent(f'''\
        Client: p4_client1

        Owner: user

        Description:
        \tCreated by user

        Root:\t{root_dir}

        Options:\trmdir compress

        LineEnd:\tlocal

        View:
        \t//depot/trunk/... //p4_client1/...
        ''')
        self._incremental(client_stdin=client_spec)

    def test_mode_incremental_parent_workdir(self):
        self.setup_step(P4(p4port='localhost:12000', mode='incremental',
                          p4base='//depot', p4branch='trunk',
                          p4user='user', p4client='p4_client1', p4passwd='pass',
                          workdir='../another_wkdir'))

        root_dir = '/home/user/another_wkdir'
        if _is_windows:
            root_dir = r'C:\Users\username\another_wkdir'
        client_spec = textwrap.dedent(f'''\
        Client: p4_client1

        Owner: user

        Description:
        \tCreated by user

        Root:\t{root_dir}

        Options:\tallwrite rmdir

        LineEnd:\tlocal

        View:
        \t//depot/trunk/... //p4_client1/...
        ''')
        self._incremental(client_stdin=client_spec, workdir='../another_wkdir')

    def test_mode_incremental_p4extra_args(self):
        self.setup_step(P4(p4port='localhost:12000', mode='incremental',
                          p4base='//depot', p4branch='trunk',
                          p4user='user', p4client='p4_client1', p4passwd='pass',
                          p4extra_args=['-Zproxyload']))

        root_dir = '/home/user/workspace/wkdir'
        if _is_windows:
            root_dir = r'C:\Users\username\Workspace\wkdir'
        client_spec = textwrap.dedent(f'''\
        Client: p4_client1

        Owner: user

        Description:
        \tCreated by user

        Root:\t{root_dir}

        Options:\tallwrite rmdir

        LineEnd:\tlocal

        View:
        \t//depot/trunk/... //p4_client1/...
        ''')
        self._incremental(client_stdin=client_spec, extra_args=['-Zproxyload'])

    def test_mode_incremental_timeout(self):
        self.setup_step(P4(p4port='localhost:12000', mode='incremental',
                          p4base='//depot', p4branch='trunk',
                          p4user='user', p4client='p4_client1', p4passwd='pass',
                          timeout=60 * 60))

        root_dir = '/home/user/workspace/wkdir'
        if _is_windows:
            root_dir = r'C:\Users\username\Workspace\wkdir'
        client_spec = textwrap.dedent(f'''\
        Client: p4_client1

        Owner: user

        Description:
        \tCreated by user

        Root:\t{root_dir}

        Options:\tallwrite rmdir

        LineEnd:\tlocal

        View:
        \t//depot/trunk/... //p4_client1/...
        ''')
        self._incremental(client_stdin=client_spec, timeout=60 * 60)

    def test_mode_incremental_stream(self):
        self.setup_step(P4(p4port='localhost:12000', mode='incremental',
                          p4base='//depot', p4branch='trunk',
                          p4user='user', p4client='p4_client1', p4passwd='pass',
                          stream=True))

        root_dir = '/home/user/workspace/wkdir'
        if _is_windows:
            root_dir = r'C:\Users\username\Workspace\wkdir'
        client_spec = textwrap.dedent(f'''\
        Client: p4_client1

        Owner: user

        Description:
        \tCreated by user

        Root:\t{root_dir}

        Options:\tallwrite rmdir

        LineEnd:\tlocal

        Stream:\t//depot/trunk
        ''')
        self._incremental(client_stdin=client_spec)

    def _full(self, client_stdin='', p4client='p4_client1', p4user='user',
              workdir='wkdir', extra_args=None, obfuscated_pass=True):
        if extra_args is None:
            extra_args = []
        if obfuscated_pass:
            expected_pass = ('obfuscated', 'pass', 'XXXXXX')
        else:
            expected_pass = 'pass'

        self.expect_commands(
            ExpectShell(workdir=workdir,
                        command=['p4', '-V'])  # expected remote command
            .exit(0),  # expected exit status

            ExpectShell(workdir=workdir,
                        command=['p4', '-p', 'localhost:12000', '-u', p4user,
                                 '-P', expected_pass,
                                 '-c', p4client, 'client', '-i'],
                        initial_stdin=client_stdin)
            .exit(0),
            ExpectShell(workdir=workdir,
                        command=['p4', '-p', 'localhost:12000', '-u', p4user,
                                 '-P', expected_pass, '-c', p4client]
                        + extra_args
                        + ['sync', '#none'])
            .exit(0),

            ExpectRmdir(dir=workdir, log_environ=True)
            .exit(0),

            ExpectShell(workdir=workdir,
                        command=['p4', '-p', 'localhost:12000', '-u', p4user,
                                 '-P', expected_pass, '-c', p4client]
                        + extra_args + ['sync'])
            .exit(0),
            ExpectShell(workdir=workdir,
                        command=['p4', '-p', 'localhost:12000', '-u', p4user,
                                 '-P', expected_pass, '-c', p4client,
                                 'changes', '-m1', '#have'])
            .stdout("Change 100 on 2013/03/21 by user@machine \'duh\'")
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        self.expect_property('got_revision', '100', 'P4')
        return self.run_step()

    def test_mode_full_p4base(self):
        self.setup_step(
            P4(p4port='localhost:12000',
               mode='full', p4base='//depot', p4branch='trunk',
               p4user='user', p4client='p4_client1', p4passwd='pass'))

        root_dir = '/home/user/workspace/wkdir'
        if _is_windows:
            root_dir = r'C:\Users\username\Workspace\wkdir'
        client_stdin = textwrap.dedent(f'''\
        Client: p4_client1

        Owner: user

        Description:
        \tCreated by user

        Root:\t{root_dir}

        Options:\tallwrite rmdir

        LineEnd:\tlocal

        View:
        \t//depot/trunk/... //p4_client1/...\n''')
        self._full(client_stdin=client_stdin)

    def test_mode_full_p4base_not_obfuscated(self):
        self.setup_step(
            P4(p4port='localhost:12000',
               mode='full', p4base='//depot', p4branch='trunk',
               p4user='user', p4client='p4_client1', p4passwd='pass'),
            worker_version={'*': '2.15'})

        root_dir = '/home/user/workspace/wkdir'
        if _is_windows:
            root_dir = r'C:\Users\username\Workspace\wkdir'
        client_stdin = textwrap.dedent(f'''\
        Client: p4_client1

        Owner: user

        Description:
        \tCreated by user

        Root:\t{root_dir}

        Options:\tallwrite rmdir

        LineEnd:\tlocal

        View:
        \t//depot/trunk/... //p4_client1/...\n''')
        self._full(client_stdin=client_stdin, obfuscated_pass=False)

    def test_mode_full_p4base_with_no_branch(self):
        self.setup_step(P4(p4port='localhost:12000', mode='full',
                          p4base='//depot/trunk',
                          p4user='user', p4client='p4_client1', p4passwd='pass'))

        root_dir = '/home/user/workspace/wkdir'
        if _is_windows:
            root_dir = r'C:\Users\username\Workspace\wkdir'
        client_spec = textwrap.dedent(f'''\
        Client: p4_client1

        Owner: user

        Description:
        \tCreated by user

        Root:\t{root_dir}

        Options:\tallwrite rmdir

        LineEnd:\tlocal

        View:
        \t//depot/trunk/... //p4_client1/...
        ''')
        self._full(client_stdin=client_spec)

    def test_mode_full_p4viewspec(self):
        self.setup_step(
            P4(p4port='localhost:12000',
               mode='full',
               p4viewspec=[('//depot/main/', ''),
                           ('//depot/main/white space/', 'white space/'),
                           ('-//depot/main/white space/excluded/', 'white space/excluded/')],
               p4user='user', p4client='p4_client1', p4passwd='pass'))

        root_dir = '/home/user/workspace/wkdir'
        if _is_windows:
            root_dir = r'C:\Users\username\Workspace\wkdir'
        client_stdin = textwrap.dedent(f'''\
        Client: p4_client1

        Owner: user

        Description:
        \tCreated by user

        Root:\t{root_dir}

        Options:\tallwrite rmdir

        LineEnd:\tlocal

        View:
        \t//depot/main/... //p4_client1/...
        \t"//depot/main/white space/..." "//p4_client1/white space/..."
        \t"-//depot/main/white space/excluded/..." "//p4_client1/white space/excluded/..."
        ''')
        self._full(client_stdin=client_stdin)

    def test_mode_full_renderable_p4base(self):
        # Note that the config check skips checking p4base if it's a renderable
        self.setup_step(
            P4(p4port='localhost:12000',
               mode='full', p4base=ConstantRenderable('//depot'),
               p4branch='release/1.0', p4user='user', p4client='p4_client2',
               p4passwd='pass'))

        root_dir = '/home/user/workspace/wkdir'
        if _is_windows:
            root_dir = r'C:\Users\username\Workspace\wkdir'
        client_stdin = textwrap.dedent(f'''\
        Client: p4_client2

        Owner: user

        Description:
        \tCreated by user

        Root:\t{root_dir}

        Options:\tallwrite rmdir

        LineEnd:\tlocal

        View:
        \t//depot/release/1.0/... //p4_client2/...\n''')
        self._full(client_stdin=client_stdin, p4client='p4_client2')

    def test_mode_full_renderable_p4client(self):
        # Note that the config check skips checking p4base if it's a renderable
        self.setup_step(
            P4(p4port='localhost:12000',
               mode='full', p4base='//depot', p4branch='trunk',
               p4user='user', p4client=ConstantRenderable('p4_client_render'),
               p4passwd='pass'))

        root_dir = '/home/user/workspace/wkdir'
        if _is_windows:
            root_dir = r'C:\Users\username\Workspace\wkdir'
        client_stdin = textwrap.dedent(f'''\
        Client: p4_client_render

        Owner: user

        Description:
        \tCreated by user

        Root:\t{root_dir}

        Options:\tallwrite rmdir

        LineEnd:\tlocal

        View:
        \t//depot/trunk/... //p4_client_render/...\n''')

        self._full(client_stdin=client_stdin, p4client='p4_client_render')

    def test_mode_full_renderable_p4branch(self):
        # Note that the config check skips checking p4base if it's a renderable
        self.setup_step(
            P4(p4port='localhost:12000',
               mode='full', p4base='//depot',
               p4branch=ConstantRenderable('render_branch'),
               p4user='user', p4client='p4_client1', p4passwd='pass'))

        root_dir = '/home/user/workspace/wkdir'
        if _is_windows:
            root_dir = r'C:\Users\username\Workspace\wkdir'
        client_stdin = textwrap.dedent(f'''\
        Client: p4_client1

        Owner: user

        Description:
        \tCreated by user

        Root:\t{root_dir}

        Options:\tallwrite rmdir

        LineEnd:\tlocal

        View:
        \t//depot/render_branch/... //p4_client1/...\n''')

        self._full(client_stdin=client_stdin)

    def test_mode_full_renderable_p4viewspec(self):
        self.setup_step(
            P4(p4port='localhost:12000',
               mode='full',
               p4viewspec=[(ConstantRenderable('//depot/render_trunk/'), '')],
               p4user='different_user', p4client='p4_client1',
               p4passwd='pass'))

        root_dir = '/home/user/workspace/wkdir'
        if _is_windows:
            root_dir = r'C:\Users\username\Workspace\wkdir'
        client_stdin = textwrap.dedent(f'''\
        Client: p4_client1

        Owner: different_user

        Description:
        \tCreated by different_user

        Root:\t{root_dir}

        Options:\tallwrite rmdir

        LineEnd:\tlocal

        View:
        \t//depot/render_trunk/... //p4_client1/...\n''')

        self._full(client_stdin=client_stdin, p4user='different_user')

    def test_mode_full_p4viewspec_suffix(self):
        self.setup_step(P4(p4port='localhost:12000', mode='full',
                          p4viewspec_suffix=None,
                          p4viewspec=[('//depot/trunk/foo.xml', 'bar.xml'),
                                      ('//depot/trunk/white space/...',
                                       'white space/...'),
                                      ('-//depot/trunk/white space/excluded/...',
                                       'white space/excluded/...')],
                          p4user='user', p4client='p4_client1', p4passwd='pass'))

        root_dir = '/home/user/workspace/wkdir'
        if _is_windows:
            root_dir = r'C:\Users\username\Workspace\wkdir'
        client_spec = textwrap.dedent(f'''\
        Client: p4_client1

        Owner: user

        Description:
        \tCreated by user

        Root:\t{root_dir}

        Options:\tallwrite rmdir

        LineEnd:\tlocal

        View:
        \t//depot/trunk/foo.xml //p4_client1/bar.xml
        \t"//depot/trunk/white space/..." "//p4_client1/white space/..."
        \t"-//depot/trunk/white space/excluded/..." "//p4_client1/white space/excluded/..."
        ''')
        self._full(client_stdin=client_spec)

    def test_mode_full_p4client_spec_options(self):
        self.setup_step(P4(p4port='localhost:12000', mode='full',
                          p4base='//depot', p4branch='trunk',
                          p4client_spec_options='rmdir compress',
                          p4user='user', p4client='p4_client1', p4passwd='pass'))

        root_dir = '/home/user/workspace/wkdir'
        if _is_windows:
            root_dir = r'C:\Users\username\Workspace\wkdir'
        client_spec = textwrap.dedent(f'''\
        Client: p4_client1

        Owner: user

        Description:
        \tCreated by user

        Root:\t{root_dir}

        Options:\trmdir compress

        LineEnd:\tlocal

        View:
        \t//depot/trunk/... //p4_client1/...
        ''')
        self._full(client_stdin=client_spec)

    def test_mode_full_parent_workdir(self):
        self.setup_step(P4(p4port='localhost:12000', mode='full',
                          p4base='//depot', p4branch='trunk',
                          p4user='user', p4client='p4_client1', p4passwd='pass',
                          workdir='../another_wkdir'))

        root_dir = '/home/user/another_wkdir'
        if _is_windows:
            root_dir = r'C:\Users\username\another_wkdir'
        client_spec = textwrap.dedent(f'''\
        Client: p4_client1

        Owner: user

        Description:
        \tCreated by user

        Root:\t{root_dir}

        Options:\tallwrite rmdir

        LineEnd:\tlocal

        View:
        \t//depot/trunk/... //p4_client1/...
        ''')
        self._full(client_stdin=client_spec, workdir='../another_wkdir')

    def test_mode_full_p4extra_args(self):
        self.setup_step(P4(p4port='localhost:12000', mode='full',
                          p4base='//depot', p4branch='trunk',
                          p4user='user', p4client='p4_client1', p4passwd='pass',
                          p4extra_args=['-Zproxyload']))

        root_dir = '/home/user/workspace/wkdir'
        if _is_windows:
            root_dir = r'C:\Users\username\Workspace\wkdir'
        client_spec = textwrap.dedent(f'''\
        Client: p4_client1

        Owner: user

        Description:
        \tCreated by user

        Root:\t{root_dir}

        Options:\tallwrite rmdir

        LineEnd:\tlocal

        View:
        \t//depot/trunk/... //p4_client1/...
        ''')
        self._full(client_stdin=client_spec, extra_args=['-Zproxyload'])

    def test_mode_full_stream(self):
        self.setup_step(P4(p4port='localhost:12000', mode='full',
                          p4base='//depot', p4branch='trunk',
                          p4user='user', p4client='p4_client1', p4passwd='pass',
                          stream=True))

        root_dir = '/home/user/workspace/wkdir'
        if _is_windows:
            root_dir = r'C:\Users\username\Workspace\wkdir'
        client_spec = textwrap.dedent(f'''\
        Client: p4_client1

        Owner: user

        Description:
        \tCreated by user

        Root:\t{root_dir}

        Options:\tallwrite rmdir

        LineEnd:\tlocal

        Stream:\t//depot/trunk
        ''')
        self._full(client_stdin=client_spec)

    def test_mode_full_stream_renderable_p4base(self):
        self.setup_step(P4(p4port='localhost:12000', mode='full',
                          p4base=ConstantRenderable('//depot'), p4branch='trunk',
                          p4user='user', p4client='p4_client1', p4passwd='pass',
                          stream=True))

        root_dir = '/home/user/workspace/wkdir'
        if _is_windows:
            root_dir = r'C:\Users\username\Workspace\wkdir'
        client_spec = textwrap.dedent(f'''\
        Client: p4_client1

        Owner: user

        Description:
        \tCreated by user

        Root:\t{root_dir}

        Options:\tallwrite rmdir

        LineEnd:\tlocal

        Stream:\t//depot/trunk
        ''')
        self._full(client_stdin=client_spec)

    def test_mode_full_stream_renderable_p4branch(self):
        self.setup_step(P4(p4port='localhost:12000', mode='full',
                          p4base='//depot', p4branch=ConstantRenderable('render_branch'),
                          p4user='user', p4client='p4_client1', p4passwd='pass',
                          stream=True))

        root_dir = '/home/user/workspace/wkdir'
        if _is_windows:
            root_dir = r'C:\Users\username\Workspace\wkdir'
        client_spec = textwrap.dedent(f'''\
        Client: p4_client1

        Owner: user

        Description:
        \tCreated by user

        Root:\t{root_dir}

        Options:\tallwrite rmdir

        LineEnd:\tlocal

        Stream:\t//depot/render_branch
        ''')
        self._full(client_stdin=client_spec)

    def test_worker_connection_lost(self):
        self.setup_step(P4(p4port='localhost:12000', mode='incremental',
                          p4base='//depot', p4branch='trunk',
                          p4user='user', p4client='p4_client1', p4passwd='pass'),
                       dict(revision='100',))

        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['p4', '-V'])
            .error(error.ConnectionLost())
        )
        self.expect_outcome(result=RETRY, state_string="update (retry)")
        return self.run_step()

    def test_ticket_auth(self):
        self.setup_step(P4(p4port='localhost:12000',
                          p4base='//depot', p4branch='trunk',
                          p4user='user', p4client='p4_client1',
                          p4passwd='pass', use_tickets=True))

        root_dir = '/home/user/workspace/wkdir'
        if _is_windows:
            root_dir = r'C:\Users\username\Workspace\wkdir'
        client_spec = textwrap.dedent(f'''\
        Client: p4_client1

        Owner: user

        Description:
        \tCreated by user

        Root:\t{root_dir}

        Options:\tallwrite rmdir

        LineEnd:\tlocal

        View:
        \t//depot/trunk/... //p4_client1/...
        ''')

        self.expect_commands(
            ExpectShell(workdir='wkdir', command=['p4', '-V'])
            .exit(0),

            # This is the extra step that gets run when using tickets,
            # and the password is not passed anymore after that.
            ExpectShell(workdir='wkdir',
                        command=['p4', '-p', 'localhost:12000', '-u', 'user',
                                 '-c', 'p4_client1', 'login'],
                        initial_stdin='pass\n')
            .exit(0),

            ExpectShell(workdir='wkdir',
                        command=['p4', '-p', 'localhost:12000', '-u', 'user',
                                 '-c', 'p4_client1', 'client', '-i'],
                        initial_stdin=client_spec)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=(['p4', '-p', 'localhost:12000', '-u', 'user',
                                  '-c', 'p4_client1', 'sync']))
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['p4', '-p', 'localhost:12000', '-u', 'user',
                                 '-c', 'p4_client1', 'changes', '-m1', '#have'])
            .stdout("Change 100 on 2013/03/21 by user@machine \'duh\'")
            .exit(0)
        )
        self.expect_outcome(result=SUCCESS)
        return self.run_step()
