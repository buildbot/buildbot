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

import os
import shutil

import buildbot_worker.runprocess
from buildbot_worker.commands import utils
from buildbot_worker.test.fake import runprocess
from buildbot_worker.test.fake import workerforbuilder


class CommandTestMixin(object):

    """
    Support for testing Command subclasses.
    """

    def setUpCommand(self):
        """
        Get things ready to test a Command

        Sets:
            self.basedir -- the basedir (an abs path)
            self.basedir_workdir -- os.path.join(self.basedir, 'workdir')
            self.basedir_source -- os.path.join(self.basedir, 'source')
        """
        self.basedir = os.path.abspath('basedir')
        self.basedir_workdir = os.path.join(self.basedir, 'workdir')
        self.basedir_source = os.path.join(self.basedir, 'source')

        # clean up the basedir unconditionally
        if os.path.exists(self.basedir):
            shutil.rmtree(self.basedir)

    def tearDownCommand(self):
        """
        Call this from the tearDown method to clean up any leftover workdirs and do
        any additional cleanup required.
        """
        # clean up the basedir unconditionally
        if os.path.exists(self.basedir):
            shutil.rmtree(self.basedir)

        # finish up the runprocess
        if hasattr(self, 'runprocess_patched') and self.runprocess_patched:
            runprocess.FakeRunProcess.test_done()

    def make_command(self, cmdclass, args, makedirs=False):
        """
        Create a new command object, creating the necessary arguments.  The
        cmdclass argument is the Command class, and args is the args dict
        to pass to its constructor.

        This always creates the WorkerForBuilder with a basedir (self.basedir).
        If makedirs is true, it will create the basedir and a workdir directory
        inside (named 'workdir').

        The resulting command is returned, but as a side-effect, the following
        attributes are set:

            self.cmd -- the command
            self.builder -- the (fake) WorkerForBuilder
        """

        # set up the workdir and basedir
        if makedirs:
            basedir_abs = os.path.abspath(os.path.join(self.basedir))
            workdir_abs = os.path.abspath(
                os.path.join(self.basedir, 'workdir'))
            if os.path.exists(basedir_abs):
                shutil.rmtree(basedir_abs)
            os.makedirs(workdir_abs)

        b = self.builder = workerforbuilder.FakeWorkerForBuilder(
            basedir=self.basedir)
        self.cmd = cmdclass(b, 'fake-stepid', args)

        return self.cmd

    def run_command(self):
        """
        Run the command created by make_command.  Returns a deferred that will fire
        on success or failure.
        """
        return self.cmd.doStart()

    def get_updates(self):
        """
        Return the updates made so far
        """
        return self.builder.updates

    def assertUpdates(self, updates, msg=None):
        """
        Asserts that self.get_updates() matches updates, ignoring elapsed time data
        """
        my_updates = []
        for update in self.get_updates():
            try:
                if "elapsed" in update:
                    continue
            except Exception:
                pass
            my_updates.append(update)
        self.assertEqual(my_updates, updates, msg)

    def add_update(self, upd):
        self.builder.updates.append(upd)

    def patch_runprocess(self, *expectations):
        """
        Patch a fake RunProcess class in, and set the given expectations.
        """
        self.patch(
            buildbot_worker.runprocess, 'RunProcess', runprocess.FakeRunProcess)
        buildbot_worker.runprocess.RunProcess.expect(*expectations)
        self.runprocess_patched = True

    def patch_getCommand(self, name, result):
        """
        Patch utils.getCommand to return RESULT for NAME
        """
        old_getCommand = utils.getCommand

        def new_getCommand(n):
            if n == name:
                return result
            return old_getCommand(n)
        self.patch(utils, 'getCommand', new_getCommand)

    def clean_environ(self):
        """
        Temporarily clean out os.environ to { 'PWD' : '.' }
        """
        self.patch(os, 'environ', {'PWD': '.'})
