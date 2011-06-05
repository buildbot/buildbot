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

import os

from twisted.internet import defer
from twisted.python import log
from twisted.protocols import basic

from buildbot import pbutil
from buildbot.util.maildir import MaildirService
from buildbot.util import netstrings
from buildbot.process.properties import Properties
from buildbot.schedulers import base
from buildbot.status.buildset import BuildSetStatus


class TryBase(base.BaseScheduler):

    def filterBuilderList(self, builderNames):
        """
        Make sure that C{builderNames} is a subset of the configured
        C{self.builderNames}, returning an empty list if not.  If
        C{builderNames} is empty, use C{self.builderNames}.

        @returns: list of builder names to build on
        """

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


class JobdirService(MaildirService):
    # NOTE: tightly coupled with Try_Jobdir, below

    def messageReceived(self, filename):
        f = self.moveToCurDir(filename)
        return self.parent.handleJobFile(filename, f)


class Try_Jobdir(TryBase):

    compare_attrs = TryBase.compare_attrs + ( 'jobdir', )

    def __init__(self, name, builderNames, jobdir,
                 properties={}):
        TryBase.__init__(self, name=name, builderNames=builderNames, properties=properties)
        self.jobdir = jobdir
        self.watcher = JobdirService()
        self.watcher.setServiceParent(self)

    def startService(self):
        # set the watcher's basedir now that we have a master
        self.watcher.setBasedir(os.path.join(self.master.basedir, self.jobdir))
        TryBase.startService(self)

    def parseJob(self, f):
        # jobfiles are serialized build requests. Each is a list of
        # serialized netstrings, in the following order:
        #  "2", the format version number ("1" does not have project/repo)
        #  buildsetID, arbitrary string, used to find the buildSet later
        #  branch name, "" for default-branch
        #  base revision, "" for HEAD
        #  patchlevel, usually "1"
        #  patch
        #  builderNames...
        p = netstrings.NetstringParser()
        try:
            p.feed(f.read())
        except basic.NetstringParseError:
            raise BadJobfile("unable to parse netstrings")
        if not p.strings:
            raise BadJobfile("could not find any complete netstrings")
        ver = p.strings.pop(0)

        if ver == "1":
            buildsetID, branch, baserev, patchlevel, diff = p.strings[:5]
            builderNames = p.strings[5:]
            if branch == "":
                branch = None
            if baserev == "":
                baserev = None
            patchlevel = int(patchlevel)
            repository=''
            project=''
            who=''
        elif ver == "2": # introduced the repository and project property
            buildsetID, branch, baserev, patchlevel, diff, repository, project = p.strings[:7]
            builderNames = p.strings[7:]
            if branch == "":
                branch = None
            if baserev == "":
                baserev = None
            patchlevel = int(patchlevel)
            who=''
        elif ver == "3": # introduced who property
            buildsetID, branch, baserev, patchlevel, diff, repository, project, who = p.strings[:8]
            builderNames = p.strings[8:]
            if branch == "":
                branch = None
            if baserev == "":
                baserev = None
            patchlevel = int(patchlevel)
        else:
            raise BadJobfile("unknown version '%s'" % ver)
        return dict(
                builderNames=builderNames,
                branch=branch,
                baserev=baserev,
                patch_body=diff,
                patch_level=patchlevel,
                repository=repository,
                project=project,
                who=who,
                jobid=buildsetID)

    def handleJobFile(self, filename, f):
        try:
            parsed_job = self.parseJob(f)
            builderNames = parsed_job['builderNames']
        except BadJobfile:
            log.msg("%s reports a bad jobfile in %s" % (self, filename))
            log.err()
            return defer.succeed(None)

        # Validate/fixup the builder names.
        builderNames = self.filterBuilderList(builderNames)
        if not builderNames:
            log.msg("incoming Try job did not specify any allowed builder names")
            return defer.succeed(None)

        d = self.master.db.sourcestamps.addSourceStamp(
                branch=parsed_job['branch'],
                revision=parsed_job['baserev'],
                patch_body=parsed_job['patch_body'],
                patch_level=parsed_job['patch_level'],
                patch_subdir='', # TODO: can't set this remotely - #1769
                project=parsed_job['project'],
                repository=parsed_job['repository'])
        def create_buildset(ssid):
            reason = "'try' job"
            if parsed_job['who']:
                reason += " by user %s" % parsed_job['who']
            return self.addBuildsetForSourceStamp(ssid=ssid,
                    reason=reason, external_idstring=parsed_job['jobid'],
                    builderNames=builderNames)
        d.addCallback(create_buildset)
        return d


class Try_Userpass_Perspective(pbutil.NewCredPerspective):
    def __init__(self, scheduler, username):
        self.scheduler = scheduler
        self.username = username

    @defer.deferredGenerator
    def perspective_try(self, branch, revision, patch, repository, project,
                        builderNames, who='', properties={} ):
        db = self.scheduler.master.db
        log.msg("user %s requesting build on builders %s" % (self.username,
                                                             builderNames))

        # build the intersection of the request and our configured list
        builderNames = self.scheduler.filterBuilderList(builderNames)
        if not builderNames:
            return

        wfd = defer.waitForDeferred(
                db.sourcestamps.addSourceStamp(branch=branch, revision=revision,
                    repository=repository, project=project, patch_level=patch[0],
                    patch_body=patch[1], patch_subdir=''))
                    # note: no way to specify patch subdir - #1769
        yield wfd
        ssid = wfd.getResult()

        reason = "'try' job"
        if who:
            reason += " by user %s" % who

        requested_props = Properties()
        requested_props.update(properties, "try build")
        wfd = defer.waitForDeferred(
                self.scheduler.addBuildsetForSourceStamp(ssid=ssid,
                        reason=reason, properties=requested_props,
                        builderNames=builderNames))
        yield wfd
        (bsid,brids) = wfd.getResult()

        # return a remotely-usable BuildSetStatus object
        wfd = defer.waitForDeferred(
                db.buildsets.getBuildset(bsid))
        yield wfd
        bsdict = wfd.getResult()

        bss = BuildSetStatus(bsdict, self.scheduler.master.status)
        from buildbot.status.client import makeRemote
        r = makeRemote(bss)
        yield r # return value

    def perspective_getAvailableBuilderNames(self):
        # Return a list of builder names that are configured
        # for the try service
        # This is mostly intended for integrating try services
        # into other applications
        return self.scheduler.listBuilderNames()


class Try_Userpass(TryBase):
    compare_attrs = ( 'name', 'builderNames', 'port', 'userpass', 'properties' )

    def __init__(self, name, builderNames, port, userpass,
                 properties={}):
        TryBase.__init__(self, name=name, builderNames=builderNames, properties=properties)
        self.port = port
        self.userpass = userpass

    def startService(self):
        TryBase.startService(self)

        # register each user/passwd with the pbmanager
        def factory(mind, username):
            return Try_Userpass_Perspective(self, username)
        self.registrations = []
        for user, passwd in self.userpass:
            self.registrations.append(
                    self.master.pbmanager.register(self.port, user, passwd, factory))

    def stopService(self):
        d = defer.maybeDeferred(TryBase.stopService, self)
        def unreg(_):
            return defer.gatherResults(
                [ reg.unregister() for reg in self.registrations ])
        d.addCallback(unreg)
        return d
