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

from __future__ import absolute_import
from __future__ import print_function

import platform
import textwrap

from twisted.internet import error
from twisted.python import reflect
from twisted.trial import unittest

from buildbot import config
from buildbot.process.results import RETRY
from buildbot.process.results import SUCCESS
from buildbot.steps.source.p4 import P4
from buildbot.test.fake.remotecommand import Expect
from buildbot.test.fake.remotecommand import ExpectShell
from buildbot.test.util import sourcesteps
from buildbot.test.util.properties import ConstantRenderable
from buildbot.util import unicode2bytes

_is_windows = (platform.system() == 'Windows')


class TestP4(sourcesteps.SourceStepMixin, unittest.TestCase):

    def setUp(self):
        return self.setUpSourceStep()

    def tearDown(self):
        return self.tearDownSourceStep()

    def setupStep(self, step, args={}, patch=None, **kwargs):
        step = sourcesteps.SourceStepMixin.setupStep(
            self, step, args={}, patch=None, **kwargs)
        self.build.getSourceStamp().revision = args.get('revision', None)

        # builddir property used to create absolute path required in perforce
        # client spec.
        workspace_dir = '/home/user/workspace'
        if _is_windows:
            workspace_dir = r'C:\Users\username\Workspace'
            self.build.path_module = reflect.namedModule("ntpath")
        self.properties.setProperty('builddir', workspace_dir, 'P4')

    def test_no_empty_step_config(self):
        self.assertRaises(config.ConfigErrors, lambda: P4())

    def test_no_multiple_type_step_config(self):
        self.assertRaises(config.ConfigErrors, lambda:
                          P4(p4viewspec=('//depot/trunk', ''),
                             p4base='//depot', p4branch='trunk',
                             p4extra_views=['src', 'doc']))

    def test_no_p4viewspec_is_string_step_config(self):
        self.assertRaises(config.ConfigErrors, lambda:
                          P4(p4viewspec='a_bad_idea'))

    def test_no_p4base_has_trailing_slash_step_config(self):
        self.assertRaises(config.ConfigErrors, lambda:
                          P4(p4base='//depot/'))

    def test_no_p4branch_has_trailing_slash_step_config(self):
        self.assertRaises(config.ConfigErrors, lambda:
                          P4(p4base='//depot', p4branch='blah/'))

    def test_no_p4branch_with_no_p4base_step_config(self):
        self.assertRaises(config.ConfigErrors, lambda:
                          P4(p4branch='blah'))

    def test_no_p4extra_views_with_no_p4base_step_config(self):
        self.assertRaises(config.ConfigErrors, lambda:
                          P4(p4extra_views='blah'))

    def test_incorrect_mode(self):
        self.assertRaises(config.ConfigErrors, lambda:
                          P4(p4base='//depot',
                             mode='invalid'))

    def test_mode_incremental_p4base_with_revision(self):
        self.setupStep(P4(p4port='localhost:12000', mode='incremental',
                          p4base='//depot', p4branch='trunk',
                          p4user='user', p4client='p4_client1', p4passwd='pass'),
                       dict(revision='100',))

        root_dir = '/home/user/workspace/wkdir'
        if _is_windows:
            root_dir = r'C:\Users\username\Workspace\wkdir'
        client_spec = textwrap.dedent('''\
        Client: p4_client1

        Owner: user

        Description:
        \tCreated by user

        Root:\t%s

        Options:\tallwrite rmdir

        LineEnd:\tlocal

        View:
        \t//depot/trunk/... //p4_client1/...
        ''' % root_dir)
        client_spec = unicode2bytes(client_spec)

        self.expectCommands(
            ExpectShell(workdir='wkdir',  # defaults to this, only changes if it has a copy mode.
                        command=['p4', '-V'])  # expected remote command
            + 0,  # expected exit status

            ExpectShell(workdir='wkdir',
                        command=[b'p4', b'-p', b'localhost:12000', b'-u', b'user',
                                 b'-P', ('obfuscated', b'pass', 'XXXXXX'),
                                 b'-c', b'p4_client1', b'client', b'-i'],
                        initialStdin=client_spec)
            + 0,
            ExpectShell(workdir='wkdir',
                        command=[b'p4', b'-p', b'localhost:12000', b'-u', b'user',
                                 b'-P', ('obfuscated', b'pass', 'XXXXXX'),
                                 b'-c', b'p4_client1', b'sync', b'//depot...@100'])
            + 0,
            ExpectShell(workdir='wkdir',
                        command=[b'p4', b'-p', b'localhost:12000', b'-u', b'user',
                                 b'-P', ('obfuscated', b'pass', 'XXXXXX'),
                                 b'-c', b'p4_client1', b'changes', b'-m1', b'#have'])
            + ExpectShell.log('stdio',
                              stdout="Change 100 on 2013/03/21 by user@machine \'duh\'")
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty('got_revision', '100', 'P4')
        return self.runStep()

    def _incremental(self, client_stdin='', extra_args=None, workdir='wkdir', timeout=20 * 60):
        if extra_args is None:
            extra_args = []

        self.expectCommands(
            ExpectShell(workdir=workdir,
                        command=['p4', '-V'])  # expected remote command
            + 0,  # expected exit status

            ExpectShell(workdir=workdir,
                        timeout=timeout,
                        command=[b'p4', b'-p', b'localhost:12000', b'-u', b'user',
                                 b'-P', ('obfuscated', b'pass', 'XXXXXX'),
                                 b'-c', b'p4_client1', b'client', b'-i'],
                        initialStdin=client_stdin,)
            + 0,
            ExpectShell(workdir=workdir,
                        timeout=timeout,
                        command=([b'p4', b'-p', b'localhost:12000', b'-u', b'user',
                                  b'-P', ('obfuscated', b'pass', 'XXXXXX'), b'-c', b'p4_client1']
                                 + extra_args + [b'sync']))
            + 0,
            ExpectShell(workdir=workdir,
                        timeout=timeout,
                        command=[b'p4', b'-p', b'localhost:12000', b'-u', b'user',
                                 b'-P', ('obfuscated', b'pass', 'XXXXXX'),
                                 b'-c', b'p4_client1', b'changes', b'-m1', b'#have'])
            + ExpectShell.log('stdio',
                              stdout="Change 100 on 2013/03/21 by user@machine \'duh\'")
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty('got_revision', '100', 'P4')
        return self.runStep()

    def test_mode_incremental_p4base(self):
        self.setupStep(P4(p4port='localhost:12000', mode='incremental',
                          p4base='//depot', p4branch='trunk',
                          p4user='user', p4client='p4_client1', p4passwd='pass'))

        root_dir = '/home/user/workspace/wkdir'
        if _is_windows:
            root_dir = r'C:\Users\username\Workspace\wkdir'
        client_spec = textwrap.dedent('''\
        Client: p4_client1

        Owner: user

        Description:
        \tCreated by user

        Root:\t%s

        Options:\tallwrite rmdir

        LineEnd:\tlocal

        View:
        \t//depot/trunk/... //p4_client1/...
        ''' % root_dir)
        client_spec = unicode2bytes(client_spec)
        self._incremental(client_stdin=client_spec)

    def test_mode_incremental_p4base_with_no_branch(self):
        self.setupStep(P4(p4port='localhost:12000', mode='incremental',
                          p4base='//depot/trunk',
                          p4user='user', p4client='p4_client1', p4passwd='pass'))

        root_dir = '/home/user/workspace/wkdir'
        if _is_windows:
            root_dir = r'C:\Users\username\Workspace\wkdir'
        client_spec = textwrap.dedent('''\
        Client: p4_client1

        Owner: user

        Description:
        \tCreated by user

        Root:\t%s

        Options:\tallwrite rmdir

        LineEnd:\tlocal

        View:
        \t//depot/trunk/... //p4_client1/...
        ''' % root_dir)
        client_spec = unicode2bytes(client_spec)
        self._incremental(client_stdin=client_spec)

    def test_mode_incremental_p4base_with_p4extra_views(self):
        self.setupStep(P4(p4port='localhost:12000', mode='incremental',
                          p4base='//depot', p4branch='trunk',
                          p4extra_views=[('-//depot/trunk/test', 'test'),
                                         ('-//depot/trunk/doc', 'doc'),
                                         ('-//depot/trunk/white space', 'white space')],
                          p4user='user', p4client='p4_client1', p4passwd='pass'))

        root_dir = '/home/user/workspace/wkdir'
        if _is_windows:
            root_dir = r'C:\Users\username\Workspace\wkdir'
        client_spec = textwrap.dedent('''\
        Client: p4_client1

        Owner: user

        Description:
        \tCreated by user

        Root:\t%s

        Options:\tallwrite rmdir

        LineEnd:\tlocal

        View:
        \t//depot/trunk/... //p4_client1/...
        \t-//depot/trunk/test/... //p4_client1/test/...
        \t-//depot/trunk/doc/... //p4_client1/doc/...
        \t"-//depot/trunk/white space/..." "//p4_client1/white space/..."
        ''' % root_dir)
        client_spec = unicode2bytes(client_spec)
        self._incremental(client_stdin=client_spec)

    def test_mode_incremental_p4viewspec(self):
        self.setupStep(P4(p4port='localhost:12000', mode='incremental',
                          p4viewspec=[('//depot/trunk/', ''),
                                      ('//depot/white space/', 'white space/'),
                                      ('-//depot/white space/excluded/', 'white space/excluded/')],
                          p4user='user', p4client='p4_client1', p4passwd='pass'))

        root_dir = '/home/user/workspace/wkdir'
        if _is_windows:
            root_dir = r'C:\Users\username\Workspace\wkdir'
        client_spec = textwrap.dedent('''\
        Client: p4_client1

        Owner: user

        Description:
        \tCreated by user

        Root:\t%s

        Options:\tallwrite rmdir

        LineEnd:\tlocal

        View:
        \t//depot/trunk/... //p4_client1/...
        \t"//depot/white space/..." "//p4_client1/white space/..."
        \t"-//depot/white space/excluded/..." "//p4_client1/white space/excluded/..."
        ''' % root_dir)
        client_spec = unicode2bytes(client_spec)
        self._incremental(client_stdin=client_spec)

    def test_mode_incremental_p4viewspec_suffix(self):
        self.setupStep(P4(p4port='localhost:12000', mode='incremental',
                          p4viewspec_suffix=None,
                          p4viewspec=[('//depot/trunk/foo.xml', 'bar.xml'),
                                      ('//depot/white space/...',
                                       'white space/...'),
                                      ('-//depot/white space/excluded/...', 'white space/excluded/...')],
                          p4user='user', p4client='p4_client1', p4passwd='pass'))

        root_dir = '/home/user/workspace/wkdir'
        if _is_windows:
            root_dir = r'C:\Users\username\Workspace\wkdir'
        client_spec = textwrap.dedent('''\
        Client: p4_client1

        Owner: user

        Description:
        \tCreated by user

        Root:\t%s

        Options:\tallwrite rmdir

        LineEnd:\tlocal

        View:
        \t//depot/trunk/foo.xml //p4_client1/bar.xml
        \t"//depot/white space/..." "//p4_client1/white space/..."
        \t"-//depot/white space/excluded/..." "//p4_client1/white space/excluded/..."
        ''' % root_dir)
        client_spec = unicode2bytes(client_spec)
        self._incremental(client_stdin=client_spec)

    def test_mode_incremental_p4client_spec_options(self):
        self.setupStep(P4(p4port='localhost:12000', mode='incremental',
                          p4base='//depot', p4branch='trunk',
                          p4client_spec_options='rmdir compress',
                          p4user='user', p4client='p4_client1', p4passwd='pass'))

        root_dir = '/home/user/workspace/wkdir'
        if _is_windows:
            root_dir = r'C:\Users\username\Workspace\wkdir'
        client_spec = textwrap.dedent('''\
        Client: p4_client1

        Owner: user

        Description:
        \tCreated by user

        Root:\t%s

        Options:\trmdir compress

        LineEnd:\tlocal

        View:
        \t//depot/trunk/... //p4_client1/...
        ''' % root_dir)
        client_spec = unicode2bytes(client_spec)
        self._incremental(client_stdin=client_spec)

    def test_mode_incremental_parent_workdir(self):
        self.setupStep(P4(p4port='localhost:12000', mode='incremental',
                          p4base='//depot', p4branch='trunk',
                          p4user='user', p4client='p4_client1', p4passwd='pass',
                          workdir='../another_wkdir'))

        root_dir = '/home/user/another_wkdir'
        if _is_windows:
            root_dir = r'C:\Users\username\another_wkdir'
        client_spec = textwrap.dedent('''\
        Client: p4_client1

        Owner: user

        Description:
        \tCreated by user

        Root:\t%s

        Options:\tallwrite rmdir

        LineEnd:\tlocal

        View:
        \t//depot/trunk/... //p4_client1/...
        ''' % root_dir)
        client_spec = unicode2bytes(client_spec)
        self._incremental(client_stdin=client_spec, workdir='../another_wkdir')

    def test_mode_incremental_p4extra_args(self):
        self.setupStep(P4(p4port='localhost:12000', mode='incremental',
                          p4base='//depot', p4branch='trunk',
                          p4user='user', p4client='p4_client1', p4passwd='pass',
                          p4extra_args=['-Zproxyload']))

        root_dir = '/home/user/workspace/wkdir'
        if _is_windows:
            root_dir = r'C:\Users\username\Workspace\wkdir'
        client_spec = textwrap.dedent('''\
        Client: p4_client1

        Owner: user

        Description:
        \tCreated by user

        Root:\t%s

        Options:\tallwrite rmdir

        LineEnd:\tlocal

        View:
        \t//depot/trunk/... //p4_client1/...
        ''' % root_dir)
        client_spec = unicode2bytes(client_spec)
        self._incremental(client_stdin=client_spec, extra_args=[b'-Zproxyload'])

    def test_mode_incremental_timeout(self):
        self.setupStep(P4(p4port='localhost:12000', mode='incremental',
                          p4base='//depot', p4branch='trunk',
                          p4user='user', p4client='p4_client1', p4passwd='pass',
                          timeout=60 * 60))

        root_dir = '/home/user/workspace/wkdir'
        if _is_windows:
            root_dir = r'C:\Users\username\Workspace\wkdir'
        client_spec = textwrap.dedent('''\
        Client: p4_client1

        Owner: user

        Description:
        \tCreated by user

        Root:\t%s

        Options:\tallwrite rmdir

        LineEnd:\tlocal

        View:
        \t//depot/trunk/... //p4_client1/...
        ''' % root_dir)
        client_spec = unicode2bytes(client_spec)
        self._incremental(client_stdin=client_spec, timeout=60 * 60)

    def _full(self, client_stdin='', p4client=b'p4_client1', p4user=b'user',
              workdir='wkdir', extra_args=None, obfuscated_pass=True):
        if extra_args is None:
            extra_args = []
        if obfuscated_pass:
            expected_pass = ('obfuscated', b'pass', 'XXXXXX')
        else:
            expected_pass = b'pass'

        self.expectCommands(
            ExpectShell(workdir=workdir,
                        command=['p4', '-V'])  # expected remote command
            + 0,  # expected exit status

            ExpectShell(workdir=workdir,
                        command=[b'p4', b'-p', b'localhost:12000', b'-u', p4user,
                                 b'-P', expected_pass,
                                 b'-c', p4client, b'client', b'-i'],
                        initialStdin=client_stdin)
            + 0,
            ExpectShell(workdir=workdir,
                        command=[b'p4', b'-p', b'localhost:12000', b'-u', p4user,
                                 b'-P', expected_pass, b'-c', p4client]
                        + extra_args
                        + [b'sync', b'#none'])
            + 0,

            Expect('rmdir', {'dir': workdir, 'logEnviron': True})
            + 0,

            ExpectShell(workdir=workdir,
                        command=[b'p4', b'-p', b'localhost:12000', b'-u', p4user,
                                 b'-P', expected_pass, b'-c', p4client]
                        + extra_args + [b'sync'])
            + 0,
            ExpectShell(workdir=workdir,
                        command=[b'p4', b'-p', b'localhost:12000', b'-u', p4user,
                                 b'-P', expected_pass, b'-c', p4client,
                                 b'changes', b'-m1', b'#have'])
            + ExpectShell.log('stdio',
                              stdout="Change 100 on 2013/03/21 by user@machine \'duh\'")
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        self.expectProperty('got_revision', '100', 'P4')
        return self.runStep()

    def test_mode_full_p4base(self):
        self.setupStep(
            P4(p4port='localhost:12000',
               mode='full', p4base='//depot', p4branch='trunk',
               p4user='user', p4client='p4_client1', p4passwd='pass'))

        root_dir = '/home/user/workspace/wkdir'
        if _is_windows:
            root_dir = r'C:\Users\username\Workspace\wkdir'
        client_stdin = textwrap.dedent('''\
        Client: p4_client1

        Owner: user

        Description:
        \tCreated by user

        Root:\t%s

        Options:\tallwrite rmdir

        LineEnd:\tlocal

        View:
        \t//depot/trunk/... //p4_client1/...\n''' % root_dir)
        client_stdin = unicode2bytes(client_stdin)
        self._full(client_stdin=client_stdin)

    def test_mode_full_p4base_not_obfuscated(self):
        self.setupStep(
            P4(p4port='localhost:12000',
               mode='full', p4base='//depot', p4branch='trunk',
               p4user='user', p4client='p4_client1', p4passwd='pass'),
            worker_version={'*': '2.15'})

        root_dir = '/home/user/workspace/wkdir'
        if _is_windows:
            root_dir = r'C:\Users\username\Workspace\wkdir'
        client_stdin = textwrap.dedent('''\
        Client: p4_client1

        Owner: user

        Description:
        \tCreated by user

        Root:\t%s

        Options:\tallwrite rmdir

        LineEnd:\tlocal

        View:
        \t//depot/trunk/... //p4_client1/...\n''' % root_dir)
        client_stdin = unicode2bytes(client_stdin)
        self._full(client_stdin=client_stdin, obfuscated_pass=False)

    def test_mode_full_p4base_with_no_branch(self):
        self.setupStep(P4(p4port='localhost:12000', mode='full',
                          p4base='//depot/trunk',
                          p4user='user', p4client='p4_client1', p4passwd='pass'))

        root_dir = '/home/user/workspace/wkdir'
        if _is_windows:
            root_dir = r'C:\Users\username\Workspace\wkdir'
        client_spec = textwrap.dedent('''\
        Client: p4_client1

        Owner: user

        Description:
        \tCreated by user

        Root:\t%s

        Options:\tallwrite rmdir

        LineEnd:\tlocal

        View:
        \t//depot/trunk/... //p4_client1/...
        ''' % root_dir)
        client_spec = unicode2bytes(client_spec)
        self._full(client_stdin=client_spec)

    def test_mode_full_p4viewspec(self):
        self.setupStep(
            P4(p4port='localhost:12000',
               mode='full',
               p4viewspec=[('//depot/main/', ''),
                           ('//depot/main/white space/', 'white space/'),
                           ('-//depot/main/white space/excluded/', 'white space/excluded/')],
               p4user='user', p4client='p4_client1', p4passwd='pass'))

        root_dir = '/home/user/workspace/wkdir'
        if _is_windows:
            root_dir = r'C:\Users\username\Workspace\wkdir'
        client_stdin = textwrap.dedent('''\
        Client: p4_client1

        Owner: user

        Description:
        \tCreated by user

        Root:\t%s

        Options:\tallwrite rmdir

        LineEnd:\tlocal

        View:
        \t//depot/main/... //p4_client1/...
        \t"//depot/main/white space/..." "//p4_client1/white space/..."
        \t"-//depot/main/white space/excluded/..." "//p4_client1/white space/excluded/..."
        ''' % root_dir)
        client_stdin = unicode2bytes(client_stdin)
        self._full(client_stdin=client_stdin)

    def test_mode_full_renderable_p4base(self):
        # Note that the config check skips checking p4base if it's a renderable
        self.setupStep(
            P4(p4port='localhost:12000',
               mode='full', p4base=ConstantRenderable('//depot'),
               p4branch='release/1.0', p4user='user', p4client='p4_client2',
               p4passwd='pass'))

        root_dir = '/home/user/workspace/wkdir'
        if _is_windows:
            root_dir = r'C:\Users\username\Workspace\wkdir'
        client_stdin = textwrap.dedent('''\
        Client: p4_client2

        Owner: user

        Description:
        \tCreated by user

        Root:\t%s

        Options:\tallwrite rmdir

        LineEnd:\tlocal

        View:
        \t//depot/release/1.0/... //p4_client2/...\n''' % root_dir)
        client_stdin = unicode2bytes(client_stdin)
        self._full(client_stdin=client_stdin, p4client=b'p4_client2')

    def test_mode_full_renderable_p4client(self):
        # Note that the config check skips checking p4base if it's a renderable
        self.setupStep(
            P4(p4port='localhost:12000',
               mode='full', p4base='//depot', p4branch='trunk',
               p4user='user', p4client=ConstantRenderable('p4_client_render'),
               p4passwd='pass'))

        root_dir = '/home/user/workspace/wkdir'
        if _is_windows:
            root_dir = r'C:\Users\username\Workspace\wkdir'
        client_stdin = textwrap.dedent('''\
        Client: p4_client_render

        Owner: user

        Description:
        \tCreated by user

        Root:\t%s

        Options:\tallwrite rmdir

        LineEnd:\tlocal

        View:
        \t//depot/trunk/... //p4_client_render/...\n''' % root_dir)
        client_stdin = unicode2bytes(client_stdin)

        self._full(client_stdin=client_stdin, p4client=b'p4_client_render')

    def test_mode_full_renderable_p4branch(self):
        # Note that the config check skips checking p4base if it's a renderable
        self.setupStep(
            P4(p4port='localhost:12000',
               mode='full', p4base='//depot',
               p4branch=ConstantRenderable('render_branch'),
               p4user='user', p4client='p4_client1', p4passwd='pass'))

        root_dir = '/home/user/workspace/wkdir'
        if _is_windows:
            root_dir = r'C:\Users\username\Workspace\wkdir'
        client_stdin = textwrap.dedent('''\
        Client: p4_client1

        Owner: user

        Description:
        \tCreated by user

        Root:\t%s

        Options:\tallwrite rmdir

        LineEnd:\tlocal

        View:
        \t//depot/render_branch/... //p4_client1/...\n''' % root_dir)
        client_stdin = unicode2bytes(client_stdin)

        self._full(client_stdin=client_stdin)

    def test_mode_full_renderable_p4viewspec(self):
        self.setupStep(
            P4(p4port='localhost:12000',
               mode='full',
               p4viewspec=[(ConstantRenderable('//depot/render_trunk/'), '')],
               p4user='different_user', p4client='p4_client1',
               p4passwd='pass'))

        root_dir = '/home/user/workspace/wkdir'
        if _is_windows:
            root_dir = r'C:\Users\username\Workspace\wkdir'
        client_stdin = textwrap.dedent('''\
        Client: p4_client1

        Owner: different_user

        Description:
        \tCreated by different_user

        Root:\t%s

        Options:\tallwrite rmdir

        LineEnd:\tlocal

        View:
        \t//depot/render_trunk/... //p4_client1/...\n''' % root_dir)
        client_stdin = unicode2bytes(client_stdin)

        self._full(client_stdin=client_stdin, p4user=b'different_user')

    def test_mode_full_p4viewspec_suffix(self):
        self.setupStep(P4(p4port='localhost:12000', mode='full',
                          p4viewspec_suffix=None,
                          p4viewspec=[('//depot/trunk/foo.xml', 'bar.xml'),
                                      ('//depot/trunk/white space/...',
                                       'white space/...'),
                                      ('-//depot/trunk/white space/excluded/...', 'white space/excluded/...')],
                          p4user='user', p4client='p4_client1', p4passwd='pass'))

        root_dir = '/home/user/workspace/wkdir'
        if _is_windows:
            root_dir = r'C:\Users\username\Workspace\wkdir'
        client_spec = textwrap.dedent('''\
        Client: p4_client1

        Owner: user

        Description:
        \tCreated by user

        Root:\t%s

        Options:\tallwrite rmdir

        LineEnd:\tlocal

        View:
        \t//depot/trunk/foo.xml //p4_client1/bar.xml
        \t"//depot/trunk/white space/..." "//p4_client1/white space/..."
        \t"-//depot/trunk/white space/excluded/..." "//p4_client1/white space/excluded/..."
        ''' % root_dir)
        client_spec = unicode2bytes(client_spec)
        self._full(client_stdin=client_spec)

    def test_mode_full_p4client_spec_options(self):
        self.setupStep(P4(p4port='localhost:12000', mode='full',
                          p4base='//depot', p4branch='trunk',
                          p4client_spec_options='rmdir compress',
                          p4user='user', p4client='p4_client1', p4passwd='pass'))

        root_dir = '/home/user/workspace/wkdir'
        if _is_windows:
            root_dir = r'C:\Users\username\Workspace\wkdir'
        client_spec = textwrap.dedent('''\
        Client: p4_client1

        Owner: user

        Description:
        \tCreated by user

        Root:\t%s

        Options:\trmdir compress

        LineEnd:\tlocal

        View:
        \t//depot/trunk/... //p4_client1/...
        ''' % root_dir)
        client_spec = unicode2bytes(client_spec)
        self._full(client_stdin=client_spec)

    def test_mode_full_parent_workdir(self):
        self.setupStep(P4(p4port='localhost:12000', mode='full',
                          p4base='//depot', p4branch='trunk',
                          p4user='user', p4client='p4_client1', p4passwd='pass',
                          workdir='../another_wkdir'))

        root_dir = '/home/user/another_wkdir'
        if _is_windows:
            root_dir = r'C:\Users\username\another_wkdir'
        client_spec = textwrap.dedent('''\
        Client: p4_client1

        Owner: user

        Description:
        \tCreated by user

        Root:\t%s

        Options:\tallwrite rmdir

        LineEnd:\tlocal

        View:
        \t//depot/trunk/... //p4_client1/...
        ''' % root_dir)
        client_spec = unicode2bytes(client_spec)
        self._full(client_stdin=client_spec, workdir='../another_wkdir')

    def test_mode_full_p4extra_args(self):
        self.setupStep(P4(p4port='localhost:12000', mode='full',
                          p4base='//depot', p4branch='trunk',
                          p4user='user', p4client='p4_client1', p4passwd='pass',
                          p4extra_args=['-Zproxyload']))

        root_dir = '/home/user/workspace/wkdir'
        if _is_windows:
            root_dir = r'C:\Users\username\Workspace\wkdir'
        client_spec = textwrap.dedent('''\
        Client: p4_client1

        Owner: user

        Description:
        \tCreated by user

        Root:\t%s

        Options:\tallwrite rmdir

        LineEnd:\tlocal

        View:
        \t//depot/trunk/... //p4_client1/...
        ''' % root_dir)
        client_spec = unicode2bytes(client_spec)
        self._full(client_stdin=client_spec, extra_args=[b'-Zproxyload'])

    def test_worker_connection_lost(self):
        self.setupStep(P4(p4port='localhost:12000', mode='incremental',
                          p4base='//depot', p4branch='trunk',
                          p4user='user', p4client='p4_client1', p4passwd='pass'),
                       dict(revision='100',))

        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['p4', '-V'])
            + ('err', error.ConnectionLost()),
        )
        self.expectOutcome(result=RETRY, state_string="update (retry)")
        return self.runStep()

    def test_ticket_auth(self):
        self.setupStep(P4(p4port='localhost:12000',
                          p4base='//depot', p4branch='trunk',
                          p4user='user', p4client='p4_client1',
                          p4passwd='pass', use_tickets=True))

        root_dir = '/home/user/workspace/wkdir'
        if _is_windows:
            root_dir = r'C:\Users\username\Workspace\wkdir'
        client_spec = textwrap.dedent('''\
        Client: p4_client1

        Owner: user

        Description:
        \tCreated by user

        Root:\t%s

        Options:\tallwrite rmdir

        LineEnd:\tlocal

        View:
        \t//depot/trunk/... //p4_client1/...
        ''' % root_dir)
        client_spec = unicode2bytes(client_spec)

        self.expectCommands(
            ExpectShell(workdir='wkdir', command=['p4', '-V'])
            + 0,

            # This is the extra step that gets run when using tickets,
            # and the password is not passed anymore after that.
            ExpectShell(workdir='wkdir',
                        command=[b'p4', b'-p', b'localhost:12000', b'-u', b'user',
                                 b'-c', b'p4_client1', b'login'],
                        initialStdin='pass\n')
            + 0,

            ExpectShell(workdir='wkdir',
                        command=[b'p4', b'-p', b'localhost:12000', b'-u', b'user',
                                 b'-c', b'p4_client1', b'client', b'-i'],
                        initialStdin=client_spec)
            + 0,
            ExpectShell(workdir='wkdir',
                        command=([b'p4', b'-p', b'localhost:12000', b'-u', b'user',
                                  b'-c', b'p4_client1', b'sync']))
            + 0,
            ExpectShell(workdir='wkdir',
                        command=[b'p4', b'-p', b'localhost:12000', b'-u', b'user',
                                 b'-c', b'p4_client1', b'changes', b'-m1', b'#have'])
            + ExpectShell.log('stdio',
                              stdout="Change 100 on 2013/03/21 by user@machine \'duh\'")
            + 0,
        )
        self.expectOutcome(result=SUCCESS)
        return self.runStep()
