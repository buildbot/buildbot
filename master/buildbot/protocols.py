from twisted.protocols import amp

class DebugAMP(amp.AMP):

    def sendBox(self, box):
        print "--> ", box
        return amp.AMP.sendBox(self, box)

    def ampBoxReceived(self, box):
        print "<-- ", box
        return amp.AMP.ampBoxReceived(self, box)


class GetInfo(amp.Command):
    arguments = []
    response = [
        ('commands', amp.AmpList([
            ('key', amp.String()), # command name
            ('value', amp.String()), # version
            ])
        ),
        ('environ', amp.AmpList([
            ('key', amp.String()),
            ('value', amp.String()),
            ])
        ),
        ('system', amp.String()),
        ('basedir', amp.String()),
        ('version', amp.String()),
    ]


class SetBuilderList(amp.Command):
    """
    Given a list of builders and their build directories, ensures that those
    builders, and only those builders, are running.
    This can be called after the initial connection is established, with a new
    list, to add or remove builders.
    """
    arguments = [ ('builders', 
        amp.AmpList([
            ('name', amp.String()),
            ('dir', amp.String()),
        ]))
    ]
    response = [('builders', amp.ListOf(amp.String()))]


class RemotePrint(amp.Command):
    """
    Adds a message to the slave logfile
    """
    arguments = [('message', amp.String())]
    response = [('result', amp.Integer())] # 0 if OK, 1 if not


class RemoteStartCommand(amp.Command):
    """
    Execute a command
    """
    arguments = [
        ('environ', amp.AmpList([
            ('key', amp.String()),
            ('value', amp.String()),
            ])
        ),
        ('command', amp.String()),
        ('args', amp.ListOf(amp.String())),
        ('builder', amp.String()),
    ]
    response = [
        ('result', amp.Integer()),
        ('builder', amp.String()),
    ]


class RemoteAcceptLog(amp.Command):
    """
    Accept log from fake_slave
    """
    arguments = [
        ('builder', amp.String()),
        ('logName', amp.String()),
        ('stream', amp.String()),
        ('data', amp.String()),
    ]
    response = []
    requiresAnswer = False


class RemoteUpdateSendRC(amp.Command):
    arguments = [
        ('builder', amp.String()),
        ('rc', amp.Integer()),
    ]
    response = []
    requiresAnswer = False


class RemoteAuth(amp.Command):
    arguments = [
        ('user', amp.String()),
        ('password', amp.String()),
        ('features', amp.AmpList([
            ('key', amp.String()),
            ('value', amp.String())
            ])
        )
    ]
    response = [
        ('features', amp.AmpList([
            ('key', amp.String()),
            ('value', amp.String())
            ])
        )
    ]


class RemoteInterrupt(amp.Command):
    arguments = [('command', amp.String())]
    response = []


class RemoteSlaveShutdown(amp.Command):
    arguments = []
    response = []


class ShellBbCommand(amp.Command):
    arguments = [
        ('builder', amp.String()),
        ('command', amp.ListOf(amp.String())),
        ('workdir', amp.String()),
        ('env', amp.AmpList([
            ('key', amp.String()),
            ('value', amp.String()),
            ])
        ),
        ('initial_stdin', amp.String()),
        ('want_stdout', amp.String()),
        ('want_stderr', amp.String()),
        ('usePTY', amp.Boolean()),
        ('not_really', amp.Boolean()),
        ('timeout', amp.Float()),
        ('maxTime', amp.Float()),
        ('logfiles', amp.AmpList([
            ('key', amp.String()),
            ('value', amp.String()),
            ])
        ),
        ('follow', amp.String()),
        ('logEnviron', amp.Boolean()),
    ]
    response = [('error', amp.String())]


class UploadFileBbCommand(amp.Command):
    arguments = [
        ('builder', amp.String()),
        ('workdir', amp.String()),
        ('slavesrc', amp.String()),
        ('maxsize', amp.Integer()),
        ('keepstamp', amp.Boolean()),
    ]
    response = [('error', amp.String())]


class Chunk(amp.Command):
    arguments = [
        ('builder', amp.String()),
        ('chunk', amp.String()),
    ]
    response = []
    requiresAnswer = False


class EndData(amp.Command):
    arguments = [
        ('builder', amp.String())
    ]
    response = []
    requiresAnswer = False


class UploadDirectoryBbCommand(amp.Command):
    arguments = [
        ('builder', amp.String()),
        ('workdir', amp.String()),
        ('slavesrc', amp.String()),
        ('writer', amp.String()), # TODO
        ('maxsize', amp.Integer()),
        ('blocksize', amp.Integer()),
        ('compress', amp.String()),
    ]
    response = [('error', amp.String())]


class DownloadFileBbCommand(amp.Command):
    arguments = [
        ('builder', amp.String()),
        ('workdir', amp.String()),
        ('slavesrc', amp.String()),
        ('reader', amp.String()), # TODO
        ('maxsize', amp.Integer()),
        ('blocksize', amp.Integer()),
        ('mode', amp.Integer()),
    ]
    response = [('error', amp.String())]


class MkdirBbCommand(amp.Command):
    arguments = [
        ('builder', amp.String()),
        ('dir', amp.String()),
    ]
    response = [('error', amp.String())]


class RmdirBbCommand(amp.Command):
    arguments = [
        ('builder', amp.String()),
        ('dir', amp.String()),
        ('timeout', amp.Float()),
        ('maxtime', amp.Float()),
    ]
    response = [('error', amp.String())]


class CpdirBbCommand(amp.Command):
    arguments = [
        ('builder', amp.String()),
        ('fromdir', amp.String()),
        ('todir', amp.String()),
        ('timeout', amp.Float()),
        ('maxtime', amp.Float()),
    ]
    response = [('error', amp.String())]


class StatBbCommand(amp.Command):
    arguments = [
        ('builder', amp.String()),
        ('file', amp.String()),
        ('todir', amp.String()),
        ('timeout', amp.Float()),
        ('maxtime', amp.Float()),
    ]
    response = [('error', amp.String())]
