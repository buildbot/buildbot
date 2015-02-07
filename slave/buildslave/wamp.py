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

from autobahn.twisted.util import sleep
from autobahn.twisted.wamp import ApplicationRunner
from autobahn.twisted.wamp import ApplicationSession
from autobahn.wamp.exception import ApplicationError
from buildslave import base
from twisted.application import service

from twisted.internet import defer


class SlaveBuilderWamp(base.SlaveBuilderBase):
    pass


# RemoteCommand base implementation and base proxy
class ProxyBase(object):
    name = "remotecommand"

    def __init__(self, session, slavename, commandId):
        self.session = session
        self.slavename = slavename
        self.commandId = commandId

    @defer.inlineCallbacks
    def callRemote(self, command, *args, **kw):
        ret = yield self.session.call("org.buildbot." + self.name + "." + command,
                                      self.slavename, self.commandId,
                                      *args, **kw)
        defer.returnValue(ret)

    def notifyOnDisconnect(self, cb):
        pass

    def dontNotifyOnDisconnect(self, cb):
        pass

    def notifyDisconnected(self):
        pass


class RemoteCommandProxy(ProxyBase):
    name = "remotecommand"


class FileWriterProxy(ProxyBase):
    name = "filewriter"


class FileReaderProxy(ProxyBase):
    name = "filereader"


class BotWamp(base.BotBase):
    SlaveBuilder = SlaveBuilderWamp

    @defer.inlineCallbacks
    def remote_setBuilderList(self, builders):
        builders = yield base.BotBase.remote_setBuilderList(self, builders)
        self.builders = builders
        defer.returnValue(None)

    def remote_startCommand(self, builderName, commandId, commandName, args):
        session = self.parent.session
        slavename = self.parent.name
        rc = RemoteCommandProxy(session, slavename, commandId)
        if args.get('reader') is not None:
            args['reader'] = FileReaderProxy(session, slavename, commandId)
        if args.get('writer') is not None:
            args['writer'] = FileWriterProxy(session, slavename, commandId)

        self.builders[builderName].remote_startCommand(rc, commandId, commandName, args)


class BotApplicationSession(ApplicationSession, service.MultiService):

    def __init__(self, config):
        ApplicationSession.__init__(self)
        service.MultiService.__init__(self)
        self.config = config
        self.setServiceParent(config.extra['parent'])
        config.extra['parent'].session = self

    @defer.inlineCallbacks
    def onJoin(self, details):
        b = "org.buildslave." + self.parent.name + "."
        dl = []
        for name in ('getCommands', 'setBuilderList', 'print', 'getSlaveInfo', 'getVersion', 'shutdown', 'startCommand'):
            method = getattr(self.parent.bot, "remote_" + name)
            dl.append(self.register(method, b + name))
        while True:
            yield defer.gatherResults(dl)
            try:
                yield self.call("org.buildbot.connect_slave", self.parent.name)
            except ApplicationError as e:
                if e.error == ApplicationError.NO_SUCH_PROCEDURE:
                    yield sleep(.1)
                    continue
                else:
                    raise
            break


def make(config):

    if config:
        return BotApplicationSession(config)
    else:
        # if no config given, return a description of this WAMPlet ..
        return {'label': 'Buildbot slave wamplet',
                'description': 'This contains all the wamp methods provided by a buildbot slave'}


class WampBuildSlave(base.BuildSlaveBase):
    Bot = BotWamp

    def __init__(self, router_url, realm, name, passwd, basedir,
                 usePTY, umask=None,
                 unicode_encoding=None, **kw):

        base.BuildSlaveBase.__init__(self, name, basedir, usePTY, umask=umask,
                                     unicode_encoding=unicode_encoding)
        self.passwd = passwd
        self.app = ApplicationRunner(
            url=router_url,
            realm=realm,
            extra=dict(parent=self),
            debug=kw.get('debug_websockets', False),
            debug_wamp=kw.get('debug_lowlevel', False),
            debug_app=kw.get('debug', False)
        )

    def startService(self):
        self.app.run(make, start_reactor=False)
        base.BuildSlaveBase.startService(self)
