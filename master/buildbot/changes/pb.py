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

from twisted.internet import defer
from twisted.python import log

from buildbot import config
from buildbot.changes import base
from buildbot.pbutil import NewCredPerspective
from buildbot.util import service


class ChangePerspective(NewCredPerspective):

    def __init__(self, master, prefix):
        self.master = master
        self.prefix = prefix

    def attached(self, mind):
        return self

    def detached(self, mind):
        pass

    def perspective_addChange(self, changedict):
        log.msg("perspective_addChange called")

        if 'revlink' in changedict and not changedict['revlink']:
            changedict['revlink'] = ''
        if 'repository' in changedict and not changedict['repository']:
            changedict['repository'] = ''
        if 'project' in changedict and not changedict['project']:
            changedict['project'] = ''
        if 'files' not in changedict or not changedict['files']:
            changedict['files'] = []

        # rename arguments to new names.  Note that the client still uses the
        # "old" names (who, when, and isdir), as they are not deprecated yet,
        # although the master will accept the new names (author,
        # when_timestamp).  After a few revisions have passed, we
        # can switch the client to use the new names.
        if 'who' in changedict:
            changedict['author'] = changedict['who']
            del changedict['who']
        if 'when' in changedict:
            changedict['when_timestamp'] = changedict['when']
            del changedict['when']

        # turn any bytestring keys into unicode, assuming utf8 but just
        # replacing unknown characters.  Ideally client would send us unicode
        # in the first place, but older clients do not, so this fallback is
        # useful.
        for key in changedict:
            if isinstance(changedict[key], bytes):
                changedict[key] = changedict[key].decode('utf8', 'replace')
        changedict['files'] = list(changedict['files'])
        for i, file in enumerate(changedict.get('files', [])):
            if isinstance(file, bytes):
                changedict['files'][i] = file.decode('utf8', 'replace')

        files = []
        for path in changedict['files']:
            if self.prefix:
                if not path.startswith(self.prefix):
                    # this file does not start with the prefix, so ignore it
                    continue
                path = path[len(self.prefix):]
            files.append(path)
        changedict['files'] = files

        if not files:
            log.msg("No files listed in change... bit strange, but not fatal.")

        if "links" in changedict:
            log.msg("Found links: " + repr(changedict['links']))
            del changedict['links']

        d = self.master.data.updates.addChange(**changedict)

        # set the return value to None, so we don't get users depending on
        # getting a changeid
        d.addCallback(lambda _: None)
        return d


class PBChangeSource(base.ChangeSource):
    compare_attrs = ("user", "passwd", "port", "prefix", "port")

    def __init__(self, user="change", passwd="changepw", port=None,
                 prefix=None, name=None):

        if name is None:
            if prefix:
                name = "PBChangeSource:%s:%s" % (prefix, port)
            else:
                name = "PBChangeSource:%s" % (port,)

        base.ChangeSource.__init__(self, name=name)

        self.user = user
        self.passwd = passwd
        self.port = port
        self.prefix = prefix
        self.registration = None
        self.registered_port = None

    def describe(self):
        portname = self.registered_port
        d = "PBChangeSource listener on " + str(portname)
        if self.prefix is not None:
            d += " (prefix '%s')" % self.prefix
        return d

    def _calculatePort(self, cfg):
        # calculate the new port, defaulting to the worker's PB port if
        # none was specified
        port = self.port
        if port is None:
            port = cfg.protocols.get('pb', {}).get('port')
        return port

    @defer.inlineCallbacks
    def reconfigServiceWithBuildbotConfig(self, new_config):
        port = self._calculatePort(new_config)
        if not port:
            config.error("No port specified for PBChangeSource, and no "
                         "worker port configured")

        # and, if it's changed, re-register
        if port != self.registered_port and self.isActive():
            yield self._unregister()
            self._register(port)

        yield service.ReconfigurableServiceMixin.reconfigServiceWithBuildbotConfig(
            self, new_config)

    def activate(self):
        port = self._calculatePort(self.master.config)
        self._register(port)
        return defer.succeed(None)

    def deactivate(self):
        return self._unregister()

    def _register(self, port):
        if not port:
            return
        self.registered_port = port
        self.registration = self.master.pbmanager.register(
            port, self.user, self.passwd,
            self.getPerspective)

    def _unregister(self):
        self.registered_port = None
        if self.registration:
            reg = self.registration
            self.registration = None
            return reg.unregister()
        return defer.succeed(None)

    def getPerspective(self, mind, username):
        assert username == self.user
        return ChangePerspective(self.master, self.prefix)
