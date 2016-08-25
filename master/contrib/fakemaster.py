#!/usr/bin/env python

# usage: python fakemaster.py
#
# This starts a fake master instance listenting on port 9010
# You should then connect a buildslave to localhost:9010
# commands are read from fakemaster's stdin (one line per command) and executed
# on the buildslave. stderr/stdout from the buildslave are output on
# fakemaster's stdout/stderr.
#
# Original Author: Chris AtLee <catlee@mozilla.com>
# Licensed under the MPL version 2.0

from __future__ import print_function

import sys

from twisted.application import strports
from twisted.cred import checkers
from twisted.cred import portal
from twisted.internet import defer
from twisted.internet import reactor
from twisted.internet import stdio
from twisted.protocols import basic
from twisted.spread import pb
from zope.interface import implements

from buildbot.process.buildstep import RemoteShellCommand
from buildbot.util import service


class Dispatcher:
    implements(portal.IRealm)

    def __init__(self):
        self.names = {}

    def register(self, name, afactory):
        self.names[name] = afactory

    def unregister(self, name):
        del self.names[name]

    def requestAvatar(self, avatarID, mind, interface):
        assert interface == pb.IPerspective
        afactory = self.names.get(avatarID)
        if afactory:
            p = afactory.getPerspective()
        else:
            p = self.master.getPerspective(mind, avatarID)

        if not p:
            raise ValueError("no perspective for '%s'" % avatarID)

        d = defer.maybeDeferred(p.attached, mind)

        def _avatarAttached(_, mind):
            return (pb.IPerspective, p, lambda: p.detached(mind))
        d.addCallback(_avatarAttached, mind)
        return d


class DontCareChecker(checkers.InMemoryUsernamePasswordDatabaseDontUse):

    def requestAvatarId(self, credentials):
        return credentials.username


class FakeLog:

    def addStdout(self, data):
        sys.stdout.write(data)

    def addHeader(self, data):
        print(">>> ", data, end=' ')

    def addStderr(self, data):
        sys.stderr.write(data)


class FakeBot(pb.Avatar):
    parent = None

    def attached(self, remote):
        self.remote = remote
        remote.callRemote('print', 'attached')
        d = remote.callRemote('setBuilderList', [('shell', '.')])

        def setBuilderList_cb(builders):
            self.builder = builders['shell']
        d.addCallbacks(setBuilderList_cb)

    def detached(self, mind):
        self.parent.stdio.bot = None
        self.parent.stdio.transport.write('\ndetached\n# ')

    def messageReceivedFromSlave(self):
        pass

    def perspective_keepalive(self):
        pass

    def slaveVersion(self, name, version):
        pass

    def runCommand(self, cmd):
        cmd = RemoteShellCommand(workdir='.', command=cmd)
        cmd.worker = self
        cmd.logs['stdio'] = FakeLog()
        cmd._closeWhenFinished['stdio'] = False
        d = cmd.run(self, self.builder)
        return d


class CmdInterface(basic.LineReceiver):
    delimiter = '\n'
    bot = None

    def connectionMade(self):
        self.transport.write("# ")

    def lineReceived(self, line):
        if not self.bot:
            self.transport.write('not attached\n# ')
            return

        d = self.bot.runCommand(line)

        @d.addBoth
        def _done(res):
            self.transport.write("\n# ")


class FakeMaster(service.MasterService):

    def __init__(self, port):
        service.MasterService.__init__(self)
        self.setName("fakemaster")

        self.dispatcher = Dispatcher()
        self.dispatcher.master = self
        self.portal = p = portal.Portal(self.dispatcher)
        p.registerChecker(DontCareChecker())
        self.slavefactory = pb.PBServerFactory(p)
        self.slavePort = port
        self.stdio = CmdInterface()

    def startService(self):
        self.slavePort = strports.service(self.slavePort, self.slavefactory)
        self.slavePort.setServiceParent(self)

        stdio.StandardIO(self.stdio)
        return service.MasterService.startService(self)

    def getPerspective(self, mind, avatarID):
        self.bot = FakeBot()
        self.bot.parent = self
        self.stdio.bot = self.bot
        self.stdio.transport.write('\nattached\n# ')
        return self.bot

if __name__ == '__main__':
    m = FakeMaster("tcp:9010")
    m.startService()
    reactor.run()
