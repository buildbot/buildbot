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


from twisted.python import log
from twisted.internet import defer

from buildbot.pbutil import NewCredPerspective
from buildbot.changes import base
from buildbot.util import epoch2datetime

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
        # when_timestamp, and is_dir).  After a few revisions have passed, we
        # can switch the client to use the new names.
        if 'isdir' in changedict:
            changedict['is_dir'] = changedict['isdir']
            del changedict['isdir']
        if 'who' in changedict:
            changedict['author'] = changedict['who']
            del changedict['who']
        if 'when' in changedict:
            when = None
            if changedict['when'] is not None:
                when = epoch2datetime(changedict['when'])
            changedict['when_timestamp'] = when
            del changedict['when']

        # turn any bytestring keys into unicode, assuming utf8 but just
        # replacing unknown characters.  Ideally client would send us unicode
        # in the first place, but older clients do not, so this fallback is
        # useful.
        for key in changedict:
            if type(changedict[key]) == str:
                changedict[key] = changedict[key].decode('utf8', 'replace')
        changedict['files'] = list(changedict['files'])
        for i, file in enumerate(changedict.get('files', [])):
            if type(file) == str:
                changedict['files'][i] = file.decode('utf8', 'replace')
        for i, link in enumerate(changedict.get('links', [])):
            if type(link) == str:
                changedict['links'][i] = link.decode('utf8', 'replace')

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
        return self.master.addChange(**changedict)

class PBChangeSource(base.ChangeSource):
    compare_attrs = ["user", "passwd", "port", "prefix", "port"]

    def __init__(self, user="change", passwd="changepw", port=None,
            prefix=None):

        self.user = user
        self.passwd = passwd
        self.port = port
        self.prefix = prefix
        self.registration = None

    def describe(self):
        # TODO: when the dispatcher is fixed, report the specific port
        if self.port is not None:
            portname = self.port
        else:
            portname = "all-purpose slaveport"
        d = "PBChangeSource listener on " + str(portname)
        if self.prefix is not None:
            d += " (prefix '%s')" % self.prefix
        return d

    def startService(self):
        base.ChangeSource.startService(self)
        port = self.port
        if port is None:
            port = self.master.slavePortnum
        self.registration = self.master.pbmanager.register(
                port, self.user, self.passwd,
                self.getPerspective)

    def stopService(self):
        d = defer.maybeDeferred(base.ChangeSource.stopService, self)
        def unreg(_):
            if self.registration:
                return self.registration.unregister()
        d.addCallback(unreg)
        return d

    def getPerspective(self, mind, username):
        assert username == self.user
        return ChangePerspective(self.master, self.prefix)
