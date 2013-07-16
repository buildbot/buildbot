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
            ('name', amp.String()),
            ('version', amp.String()),
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
    response = [('result', amp.Integer())] #  0 for success, 1 or others are error codes

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
    arguments = [('line', amp.Unicode())]
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
