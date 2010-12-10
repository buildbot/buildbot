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

import os.path

from zope.interface import implements
from twisted.application import strports
from twisted.python import log, runtime
from twisted.protocols import basic
from twisted.cred import portal, checkers
from twisted.spread import pb

from buildbot import pbutil
from buildbot.sourcestamp import SourceStamp
from buildbot.changes.maildir import MaildirService
from buildbot.process.properties import Properties
from buildbot.schedulers import base
from buildbot.status.builder import BuildSetStatus


class TryBase(base.BaseScheduler):

    def run(self):
        # triggered by external events, not DB changes or timers
        return None

    def filterBuilderList(self, builderNames):
        # self.builderNames is the configured list of builders
        # available for try.  If the user supplies a list of builders,
        # it must be restricted to the configured list.  If not, build
        # on all of the configured builders.
        if builderNames:
            for b in builderNames:
                if not b in self.builderNames:
                    log.msg("%s got with builder %s" % (self, b))
                    log.msg(" but that wasn't in our list: %s"
                            % (self.builderNames,))
                    return []
        else:
            builderNames = self.builderNames
        return builderNames

class BadJobfile(Exception):
    pass

class JobFileScanner(basic.NetstringReceiver):
    def __init__(self):
        self.strings = []
        self.transport = self # so transport.loseConnection works
        self.error = False

    def stringReceived(self, s):
        self.strings.append(s)

    def loseConnection(self):
        self.error = True

class Try_Jobdir(TryBase):
    compare_attrs = ( 'name', 'builderNames', 'jobdir', 'properties' )

    def __init__(self, name, builderNames, jobdir,
                 properties={}):
        base.BaseScheduler.__init__(self, name, builderNames, properties)
        self.jobdir = jobdir
        self.watcher = MaildirService()
        self.watcher.setServiceParent(self)

    def setServiceParent(self, parent):
        sm = parent
        m = sm.parent
        self.watcher.setBasedir(os.path.join(m.basedir, self.jobdir))
        TryBase.setServiceParent(self, parent)

    def parseJob(self, f):
        # jobfiles are serialized build requests. Each is a list of
        # serialized netstrings, in the following order:
        #  "1", the version number of this format
        #  buildsetID, arbitrary string, used to find the buildSet later
        #  branch name, "" for default-branch
        #  base revision, "" for HEAD
        #  patchlevel, usually "1"
        #  patch
        #  builderNames...
        p = JobFileScanner()
        p.dataReceived(f.read())
        if p.error:
            raise BadJobfile("unable to parse netstrings")
        s = p.strings
        ver = s.pop(0)
        if ver == "1":
            buildsetID, branch, baserev, patchlevel, diff = s[:5]
            builderNames = s[5:]
            if branch == "":
                branch = None
            if baserev == "":
                baserev = None
            patchlevel = int(patchlevel)
            patch = (patchlevel, diff)
            ss = SourceStamp("Old client", branch, baserev, patch)
        elif ver == "2": # introduced the repository and project property
            buildsetID, branch, baserev, patchlevel, diff, repository, project = s[:7]
            builderNames = s[7:]
            if branch == "":
                branch = None
            if baserev == "":
                baserev = None
            patchlevel = int(patchlevel)
            patch = (patchlevel, diff)
            ss = SourceStamp(branch, baserev, patch, repository=repository,
                             project=project)
        else:
            raise BadJobfile("unknown version '%s'" % ver)
        return builderNames, ss, buildsetID

    def messageReceived(self, filename):
        md = os.path.join(self.parent.parent.basedir, self.jobdir)
        if runtime.platformType == "posix":
            # open the file before moving it, because I'm afraid that once
            # it's in cur/, someone might delete it at any moment
            path = os.path.join(md, "new", filename)
            f = open(path, "r")
            os.rename(os.path.join(md, "new", filename),
                      os.path.join(md, "cur", filename))
        else:
            # do this backwards under windows, because you can't move a file
            # that somebody is holding open. This was causing a Permission
            # Denied error on bear's win32-twisted1.3 buildslave.
            os.rename(os.path.join(md, "new", filename),
                      os.path.join(md, "cur", filename))
            path = os.path.join(md, "cur", filename)
            f = open(path, "r")

        try:
            builderNames, ss, jobid = self.parseJob(f)
        except BadJobfile:
            log.msg("%s reports a bad jobfile in %s" % (self, filename))
            log.err()
            return
        # Validate/fixup the builder names.
        builderNames = self.filterBuilderList(builderNames)
        if not builderNames:
            return
        reason = "'try' job"
        d = self.parent.db.runInteraction(self._try, ss, builderNames, reason)
        def _done(ign):
            self.parent.loop_done() # so it will notify builder loop
        d.addCallback(_done)
        return d

    def _try(self, t, ss, builderNames, reason):
        db = self.parent.db
        ssid = db.get_sourcestampid(ss, t)
        bsid = self.create_buildset(ssid, reason, t, builderNames=builderNames)
        return bsid

class Try_Userpass(TryBase):
    compare_attrs = ( 'name', 'builderNames', 'port', 'userpass', 'properties' )
    implements(portal.IRealm)

    def __init__(self, name, builderNames, port, userpass,
                 properties={}):
        base.BaseScheduler.__init__(self, name, builderNames, properties)
        if type(port) is int:
            port = "tcp:%d" % port
        self.port = port
        self.userpass = userpass
        c = checkers.InMemoryUsernamePasswordDatabaseDontUse()
        for user,passwd in self.userpass:
            c.addUser(user, passwd)

        p = portal.Portal(self)
        p.registerChecker(c)
        f = pb.PBServerFactory(p)
        s = strports.service(port, f)
        s.setServiceParent(self)

    def getPort(self):
        # utility method for tests: figure out which TCP port we just opened.
        return self.services[0]._port.getHost().port

    def requestAvatar(self, avatarID, mind, interface):
        log.msg("%s got connection from user %s" % (self, avatarID))
        assert interface == pb.IPerspective
        p = Try_Userpass_Perspective(self, avatarID)
        return (pb.IPerspective, p, lambda: None)

class Try_Userpass_Perspective(pbutil.NewCredPerspective):
    def __init__(self, parent, username):
        self.parent = parent
        self.username = username

    def perspective_try(self, branch, revision, patch, repository, project,
                        builderNames, properties={}, ):
        log.msg("user %s requesting build on builders %s" % (self.username,
                                                             builderNames))
        # build the intersection of the request and our configured list
        builderNames = self.parent.filterBuilderList(builderNames)
        if not builderNames:
            return
        ss = SourceStamp(branch, revision, patch, repository=repository,
                         project=project)
        reason = "'try' job from user %s" % self.username

        # roll the specified props in with our inherited props
        combined_props = Properties()
        combined_props.updateFromProperties(self.parent.properties)
        combined_props.update(properties, "try build")

        status = self.parent.parent.parent.status
        db = self.parent.parent.db
        d = db.runInteraction(self._try, ss, builderNames, reason,
                              combined_props, db)
        def _done(bsid):
            # return a remotely-usable BuildSetStatus object
            bss = BuildSetStatus(bsid, status, db)
            from buildbot.status.client import makeRemote
            r = makeRemote(bss)
            #self.parent.parent.loop_done() # so it will notify builder loop
            return r
        d.addCallback(_done)
        return d

    def _try(self, t, ss, builderNames, reason, combined_props, db):
        ssid = db.get_sourcestampid(ss, t)
        bsid = self.parent.create_buildset(ssid, reason, t,
                                           props=combined_props,
                                           builderNames=builderNames)
        return bsid

    def perspective_getAvailableBuilderNames(self):
        # Return a list of builder names that are configured
        # for the try service
        # This is mostly intended for integrating try services
        # into other applications
        return self.parent.listBuilderNames()
