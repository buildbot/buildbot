from buildslave import runprocess
from buildslave.test.util import command

class SourceCommandTestMixin(command.CommandTestMixin):
    """
    Support for testing Source Commands; an extension of CommandTestMixin
    """

    def make_command(self, cmdclass, args, makedirs=False):
        """
        Same as the parent class method, but this also adds some source-specific
        patches:

        * writeSourcedata - writes to self.sourcedata (self is the TestCase)
        * readSourcedata - reads from self.sourcedata
        * doClobber - invokes RunProcess(['clobber', DIRECTORY])
        * doCopy - invokes RunProcess(['copy', cmd.srcdir, cmd.workdir])
        """

        cmd = command.CommandTestMixin.make_command(self, cmdclass, args, makedirs)

        # note that these patches are to an *instance*, not a class, so there
        # is no need to use self.patch() to reverse them

        self.sourcedata = ''
        def readSourcedata():
            return self.sourcedata
        cmd.readSourcedata = readSourcedata

        def writeSourcedata(res):
            self.sourcedata = cmd.sourcedata
            return res
        cmd.writeSourcedata = writeSourcedata

        def doClobber(_, dirname):
            r = runprocess.RunProcess(self.builder,
                [ 'clobber', dirname ],
                self.builder.basedir)
            return r.start()
        cmd.doClobber = doClobber

        def doClobber(_, dirname):
            r = runprocess.RunProcess(self.builder,
                [ 'clobber', dirname ],
                self.builder.basedir)
            return r.start()
        cmd.doClobber = doClobber

        def doCopy(_):
            r = runprocess.RunProcess(self.builder,
                [ 'copy', cmd.srcdir, cmd.workdir ],
                self.builder.basedir)
            return r.start()
        cmd.doCopy = doCopy
