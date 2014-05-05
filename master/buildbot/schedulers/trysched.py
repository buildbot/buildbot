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
from twisted.protocols import basic
from twisted.python import log

from buildbot import pbutil
from buildbot.process.properties import Properties
from buildbot.schedulers import base
from buildbot.status.buildset import BuildSetStatus
from buildbot.util import json
from buildbot.util import netstrings
from buildbot.util.maildir import MaildirService


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
                if b not in self.builderNames:
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

    compare_attrs = ('jobdir',)

    def __init__(self, name, builderNames, jobdir,
                 properties={}):
        TryBase.__init__(self, name=name, builderNames=builderNames,
                         properties=properties)
        self.jobdir = jobdir
        self.watcher = JobdirService()
        self.watcher.setServiceParent(self)

    def startService(self):
        # set the watcher's basedir now that we have a master
        jobdir = os.path.join(self.master.basedir, self.jobdir)
        self.watcher.setBasedir(jobdir)
        for subdir in "cur new tmp".split():
            if not os.path.exists(os.path.join(jobdir, subdir)):
                os.mkdir(os.path.join(jobdir, subdir))
        TryBase.startService(self)

    def parseJob(self, f):
        # jobfiles are serialized build requests. Each is a list of
        # serialized netstrings, in the following order:
        #  format version number:
        #  "1" the original
        #  "2" introduces project and repository
        #  "3" introduces who
        #  "4" introduces comment
        #  "5" introduces properties and JSON serialization of values after
        #      version
        #  jobid: arbitrary string, used to find the buildSet later
        #  branch: branch name, "" for default-branch
        #  baserev: revision, "" for HEAD
        #  patch_level: usually "1"
        #  patch_body: patch to be applied for build
        #  repository
        #  project
        #  who: user requesting build
        #  comment: comment from user about diff and/or build
        #  builderNames: list of builder names
        #  properties: dict of build properties
        p = netstrings.NetstringParser()
        f.seek(0, 2)
        if f.tell() > basic.NetstringReceiver.MAX_LENGTH:
            raise BadJobfile("The patch size is greater that NetStringReceiver.MAX_LENGTH. Please Set this higher in the master.cfg")
        f.seek(0, 0)
        try:
            p.feed(f.read())
        except basic.NetstringParseError:
            raise BadJobfile("unable to parse netstrings")
        if not p.strings:
            raise BadJobfile("could not find any complete netstrings")
        ver = p.strings.pop(0)

        v1_keys = ['jobid', 'branch', 'baserev', 'patch_level', 'patch_body']
        v2_keys = v1_keys + ['repository', 'project']
        v3_keys = v2_keys + ['who']
        v4_keys = v3_keys + ['comment']
        keys = [v1_keys, v2_keys, v3_keys, v4_keys]
        # v5 introduces properties and uses JSON serialization

        parsed_job = {}

        def extract_netstrings(p, keys):
            for i, key in enumerate(keys):
                parsed_job[key] = p.strings[i]

        def postprocess_parsed_job():
            # apply defaults and handle type casting
            parsed_job['branch'] = parsed_job['branch'] or None
            parsed_job['baserev'] = parsed_job['baserev'] or None
            parsed_job['patch_level'] = int(parsed_job['patch_level'])
            for key in 'repository project who comment'.split():
                parsed_job[key] = parsed_job.get(key, '')
            parsed_job['properties'] = parsed_job.get('properties', {})

        if ver <= "4":
            i = int(ver) - 1
            extract_netstrings(p, keys[i])
            parsed_job['builderNames'] = p.strings[len(keys[i]):]
            postprocess_parsed_job()
        elif ver == "5":
            try:
                parsed_job = json.loads(p.strings[0])
            except ValueError:
                raise BadJobfile("unable to parse JSON")
            postprocess_parsed_job()
        else:
            raise BadJobfile("unknown version '%s'" % ver)
        return parsed_job

    @defer.inlineCallbacks
    def handleJobFile(self, filename, f):
        try:
            parsed_job = self.parseJob(f)
            builderNames = parsed_job['builderNames']
        except BadJobfile:
            log.msg("%s reports a bad jobfile in %s" % (self, filename))
            log.err()
            defer.returnValue(None)
            return

        # Validate/fixup the builder names.
        builderNames = self.filterBuilderList(builderNames)
        if not builderNames:
            log.msg(
                "incoming Try job did not specify any allowed builder names")
            defer.returnValue(None)
            return

        who = ""
        if parsed_job['who']:
            who = parsed_job['who']

        comment = ""
        if parsed_job['comment']:
            comment = parsed_job['comment']

        setid = yield self.master.db.sourcestampsets.addSourceStampSet()
        yield self.master.db.sourcestamps.addSourceStamp(
            sourcestampsetid=setid,
            branch=parsed_job['branch'],
            revision=parsed_job['baserev'],
            patch_body=parsed_job['patch_body'],
            patch_level=parsed_job['patch_level'],
            patch_author=who,
            patch_comment=comment,
            patch_subdir='',  # TODO: can't set this remotely - #1769
            project=parsed_job['project'],
            repository=parsed_job['repository'])

        reason = "'try' job"
        if parsed_job['who']:
            reason += " by user %s" % parsed_job['who']
        properties = parsed_job['properties']
        requested_props = Properties()
        requested_props.update(properties, "try build")
        bsid, brids = yield self.addBuildsetForSourceStamp(
            ssid=None, setid=setid,
            reason=reason,
            external_idstring=parsed_job['jobid'],
            builderNames=builderNames,
            properties=requested_props)
        defer.returnValue((bsid, brids))


class Try_Userpass_Perspective(pbutil.NewCredPerspective):

    def __init__(self, scheduler, username):
        self.scheduler = scheduler
        self.username = username

    @defer.inlineCallbacks
    def perspective_try(self, branch, revision, patch, repository, project,
                        builderNames, who="", comment="", properties={}):
        db = self.scheduler.master.db
        log.msg("user %s requesting build on builders %s" % (self.username,
                                                             builderNames))

        # build the intersection of the request and our configured list
        builderNames = self.scheduler.filterBuilderList(builderNames)
        if not builderNames:
            return

        reason = "'try' job"

        if who:
            reason += " by user %s" % who

        if comment:
            reason += " (%s)" % comment

        sourcestampsetid = yield db.sourcestampsets.addSourceStampSet()

        # note: no way to specify patch subdir - #1769
        yield db.sourcestamps.addSourceStamp(
            branch=branch, revision=revision, repository=repository,
            project=project, patch_level=patch[0], patch_body=patch[1],
            patch_subdir='', patch_author=who or '',
            patch_comment=comment or '', codebase='',
            sourcestampsetid=sourcestampsetid)

        requested_props = Properties()
        requested_props.update(properties, "try build")
        (bsid, brids) = yield self.scheduler.addBuildsetForSourceStamp(
            setid=sourcestampsetid, reason=reason,
            properties=requested_props, builderNames=builderNames)

        # return a remotely-usable BuildSetStatus object
        bsdict = yield db.buildsets.getBuildset(bsid)

        bss = BuildSetStatus(bsdict, self.scheduler.master.status)
        from buildbot.status.client import makeRemote
        defer.returnValue(makeRemote(bss))

    def perspective_getAvailableBuilderNames(self):
        # Return a list of builder names that are configured
        # for the try service
        # This is mostly intended for integrating try services
        # into other applications
        return self.scheduler.listBuilderNames()


class Try_Userpass(TryBase):
    compare_attrs = ('name', 'builderNames', 'port', 'userpass', 'properties')

    def __init__(self, name, builderNames, port, userpass,
                 properties={}):
        TryBase.__init__(self, name=name, builderNames=builderNames,
                         properties=properties)
        self.port = port
        self.userpass = userpass
        self.registrations = []

    def startService(self):
        TryBase.startService(self)

        # register each user/passwd with the pbmanager
        def factory(mind, username):
            return Try_Userpass_Perspective(self, username)
        for user, passwd in self.userpass:
            self.registrations.append(
                self.master.pbmanager.register(
                    self.port, user, passwd, factory))

    def stopService(self):
        d = defer.maybeDeferred(TryBase.stopService, self)

        def unreg(_):
            return defer.gatherResults(
                [reg.unregister() for reg in self.registrations])
        d.addCallback(unreg)
        return d
