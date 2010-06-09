import os
import shutil

from buildslave.test.fake import slavebuilder, runprocess
import buildslave.runprocess
from buildslave.commands import utils

class CommandTestMixin:
    """
    Support for testing Command subclasses.
    """

    def make_command(self, cmdclass, args):
        """
        Create a new command object, creating the necessary arguments.  The
        cmdclass argument is the Command class, and args is the args dict
        to pass to its constructor.

        If args has a 'workdir' key with value None, it will be replaced by a
        freshly created workdir.

        The resulting command is returned, but as a side-effect, the following
        attributes are set:

            self.cmd -- the command
            self.builder -- the (fake) SlaveBuilder
            self.workdir -- the workdir created if args['workdir'] is None
        """

        # set up the workdir
        self.workdir = None
        if 'workdir' in args and args['workdir'] is None:
            self.workdir = args['workdir'] = os.path.abspath('commmand-test-workdir')
            if os.path.exists(self.workdir):
                shutil.rmtree(self.workdir)
            os.makedirs(self.workdir)

        b = self.builder = slavebuilder.FakeSlaveBuilder()
        self.cmd = cmdclass(b, 'fake-stepid', args)
        return self.cmd

    def tearDownCommand(self):
        """
        Call this from the tearDown method to clean up any leftover workdirs and do
        any additional cleanup required.
        """
        # note: Twisted-2.5.0 does not have addCleanup, or we could use that here..
        if hasattr(self, 'workdir') and self.workdir and os.path.exists(self.workdir):
            shutil.rmtree(self.workdir)

        # finish up the runprocess
        if hasattr(self, 'runprocess_patched') and self.runprocess_patched:
            runprocess.FakeRunProcess.test_done()

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

    def patch_runprocess(self, *expectations):
        """
        Patch a fake RunProcess class in, and set the given expectations.
        """
        self.patch(buildslave.runprocess, 'RunProcess', runprocess.FakeRunProcess)
        buildslave.runprocess.RunProcess.expect(*expectations)
        self.runprocess_patched = True

    def patch_getcommand(self, name, result):
        """
        Patch utils.getCommand to return RESULT for NAME
        """
        old_getCommand = utils.getCommand
        def new_getCommand(n):
            if n == name: return result
            return old_getCommand(n)
        self.patch(utils, 'getCommand', new_getCommand)
