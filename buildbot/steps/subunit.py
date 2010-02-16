from unittest import TestResult

from buildbot.steps.shell import ShellCommand

class SubunitShellCommand(ShellCommand):
    """A ShellCommand that sniffs subunit output.

    Ideally not needed, and thus here to be trivially deleted. See issue #615
    """

    def __init__(self, *args, **kwargs):
        ShellCommand.__init__(self, *args, **kwargs)
        # importing here gets around an import loop
        from buildbot.process import subunitlogobserver
        self.addLogObserver('stdio', subunitlogobserver.SubunitLogObserver())
        self.progressMetrics = self.progressMetrics + ('tests', 'tests failed')
