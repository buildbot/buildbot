from buildbot.steps.shell import ShellCommand
from buildbot.status.builder import Event, SUCCESS, FAILURE

class MaxQ(ShellCommand):
    flunkOnFailure = True
    name = "maxq"

    def __init__(self, testdir=None, **kwargs):
        if not testdir:
            raise TypeError("please pass testdir")
        kwargs['command'] = 'run_maxq.py %s' % (testdir,)
        ShellCommand.__init__(self, **kwargs)
        self.addFactoryArguments(testdir=testdir)

    def startStatus(self):
        evt = Event("yellow", ['running', 'maxq', 'tests'],
                    files={'log': self.log})
        self.setCurrentActivity(evt)


    def finished(self, rc):
        self.failures = 0
        if rc:
            self.failures = 1
        output = self.log.getAll()
        self.failures += output.count('\nTEST FAILURE:')

        result = (SUCCESS, ['maxq'])

        if self.failures:
            result = (FAILURE, [str(self.failures), 'maxq', 'failures'])

        return self.stepComplete(result)

    def finishStatus(self, result):
        if self.failures:
            text = ["maxq", "failed"]
        else:
            text = ['maxq', 'tests']
        self.updateCurrentActivity(text=text)
        self.finishStatusSummary()
        self.finishCurrentActivity()


