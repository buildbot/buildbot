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
from future.utils import iteritems

import json
import os

from twisted.internet import defer
from twisted.protocols import basic
from twisted.python import log
from twisted.spread import pb

from buildbot import pbutil
from buildbot.process.properties import Properties
from buildbot.schedulers import base
from buildbot.util import ascii2unicode
from buildbot.util import bytes2NativeString
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
    # NOTE: tightly coupled with Try_Jobdir, below. We used to track it as a "parent"
    # via the MultiService API, but now we just track it as the member
    # "self.scheduler"

    def __init__(self, scheduler, basedir=None):
        self.scheduler = scheduler
        MaildirService.__init__(self, basedir)

    def messageReceived(self, filename):
        with self.moveToCurDir(filename) as f:
            rv = self.scheduler.handleJobFile(filename, f)
        return rv


class Try_Jobdir(TryBase):

    compare_attrs = ('jobdir',)

    def __init__(self, name, builderNames, jobdir, **kwargs):
        TryBase.__init__(self, name, builderNames, **kwargs)
        self.jobdir = jobdir
        self.watcher = JobdirService(scheduler=self)

    # TryBase used to be a MultiService and managed the JobdirService via a parent/child
    # relationship. We stub out the addService/removeService and just keep track of
    # JobdirService as self.watcher. We'll refactor these things later and remove
    # the need for this.
    def addService(self, child):
        pass

    def removeService(self, child):
        pass

    # activation handlers

    @defer.inlineCallbacks
    def activate(self):
        yield TryBase.activate(self)

        if not self.enabled:
            return

        # set the watcher's basedir now that we have a master
        jobdir = os.path.join(self.master.basedir, self.jobdir)
        self.watcher.setBasedir(jobdir)
        for subdir in "cur new tmp".split():
            if not os.path.exists(os.path.join(jobdir, subdir)):
                os.mkdir(os.path.join(jobdir, subdir))

        # bridge the activate/deactivate to a startService/stopService on the
        # child service
        self.watcher.startService()

    @defer.inlineCallbacks
    def deactivate(self):
        yield TryBase.deactivate(self)

        if not self.enabled:
            return

        # bridge the activate/deactivate to a startService/stopService on the
        # child service
        self.watcher.stopService()

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
            raise BadJobfile(
                "The patch size is greater that NetStringReceiver.MAX_LENGTH. Please Set this higher in the master.cfg")
        f.seek(0, 0)
        try:
            p.feed(f.read())
        except basic.NetstringParseError:
            raise BadJobfile("unable to parse netstrings")
        if not p.strings:
            raise BadJobfile("could not find any complete netstrings")
        ver = bytes2NativeString(p.strings.pop(0))

        v1_keys = ['jobid', 'branch', 'baserev', 'patch_level', 'patch_body']
        v2_keys = v1_keys + ['repository', 'project']
        v3_keys = v2_keys + ['who']
        v4_keys = v3_keys + ['comment']
        keys = [v1_keys, v2_keys, v3_keys, v4_keys]
        # v5 introduces properties and uses JSON serialization

        parsed_job = {}

        def extract_netstrings(p, keys):
            for i, key in enumerate(keys):
                parsed_job[key] = bytes2NativeString(p.strings[i])

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
            parsed_job['builderNames'] = [bytes2NativeString(s)
                                          for s in p.strings[len(keys[i]):]]
            postprocess_parsed_job()
        elif ver == "5":
            try:
                data = bytes2NativeString(p.strings[0])
                parsed_job = json.loads(data)
            except ValueError:
                raise BadJobfile("unable to parse JSON")
            postprocess_parsed_job()
        else:
            raise BadJobfile("unknown version '%s'" % ver)
        return parsed_job

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
            log.msg(
                "incoming Try job did not specify any allowed builder names")
            return defer.succeed(None)

        who = ""
        if parsed_job['who']:
            who = parsed_job['who']

        comment = ""
        if parsed_job['comment']:
            comment = parsed_job['comment']

        sourcestamp = dict(branch=parsed_job['branch'],
                           codebase='',
                           revision=parsed_job['baserev'],
                           patch_body=parsed_job['patch_body'],
                           patch_level=parsed_job['patch_level'],
                           patch_author=who,
                           patch_comment=comment,
                           # TODO: can't set this remotely - #1769
                           patch_subdir='',
                           project=parsed_job['project'],
                           repository=parsed_job['repository'])
        reason = u"'try' job"
        if parsed_job['who']:
            reason += u" by user %s" % ascii2unicode(parsed_job['who'])
        properties = parsed_job['properties']
        requested_props = Properties()
        requested_props.update(properties, "try build")

        return self.addBuildsetForSourceStamps(
            sourcestamps=[sourcestamp],
            reason=reason,
            external_idstring=ascii2unicode(parsed_job['jobid']),
            builderNames=builderNames,
            properties=requested_props)


class RemoteBuildSetStatus(pb.Referenceable):

    def __init__(self, master, bsid, brids):
        self.master = master
        self.bsid = bsid
        self.brids = brids

    @defer.inlineCallbacks
    def remote_getBuildRequests(self):
        brids = dict()
        for builderid, brid in iteritems(self.brids):
            builderDict = yield self.master.data.get(('builders', builderid))
            brids[builderDict['name']] = brid
        defer.returnValue([(n, RemoteBuildRequest(self.master, n, brid))
                           for n, brid in iteritems(brids)])


class RemoteBuildRequest(pb.Referenceable):

    def __init__(self, master, builderName, brid):
        self.master = master
        self.builderName = builderName
        self.brid = brid
        self.consumer = None

    @defer.inlineCallbacks
    def remote_subscribe(self, subscriber):
        brdict = yield self.master.data.get(('buildrequests', self.brid))
        if not brdict:
            return
        builderId = brdict['builderid']
        # make sure we aren't double-reporting any builds
        reportedBuilds = set([])

        # subscribe to any new builds..
        def gotBuild(key, msg):
            if msg['buildrequestid'] != self.brid or key[-1] != 'new':
                return
            if msg['buildid'] in reportedBuilds:
                return
            reportedBuilds.add(msg['buildid'])
            return subscriber.callRemote('newbuild',
                                         RemoteBuild(
                                             self.master, msg, self.builderName),
                                         self.builderName)
        self.consumer = yield self.master.mq.startConsuming(
            gotBuild, ('builders', str(builderId), 'builds', None, None))
        subscriber.notifyOnDisconnect(lambda _:
                                      self.remote_unsubscribe(subscriber))

        # and get any existing builds
        builds = yield self.master.data.get(('buildrequests', self.brid, 'builds'))
        for build in builds:
            if build['buildid'] in reportedBuilds:
                continue
            reportedBuilds.add(build['buildid'])
            yield subscriber.callRemote('newbuild',
                                        RemoteBuild(
                                            self.master, build, self.builderName),
                                        self.builderName)

    def remote_unsubscribe(self, subscriber):
        if self.consumer:
            self.consumer.stopConsuming()
            self.consumer = None


class RemoteBuild(pb.Referenceable):

    def __init__(self, master, builddict, builderName):
        self.master = master
        self.builddict = builddict
        self.builderName = builderName
        self.consumer = None

    @defer.inlineCallbacks
    def remote_subscribe(self, subscriber, interval):
        # subscribe to any new steps..
        def stepChanged(key, msg):
            log.msg("SC")
            if key[-1] == 'started':
                return subscriber.callRemote('stepStarted',
                                             self.builderName, self, msg['name'], None)
            elif key[-1] == 'finished':
                return subscriber.callRemote('stepFinished',
                                             self.builderName, self, msg['name'], None, msg['results'])
        self.consumer = yield self.master.mq.startConsuming(
            stepChanged,
            ('builds', str(self.builddict['buildid']), 'steps', None, None))
        subscriber.notifyOnDisconnect(lambda _:
                                      self.remote_unsubscribe(subscriber))

    def remote_unsubscribe(self, subscriber):
        if self.consumer:
            self.consumer.stopConsuming()
            self.consumer = None

    @defer.inlineCallbacks
    def remote_waitUntilFinished(self):
        d = defer.Deferred()

        def buildEvent(key, msg):
            log.msg("BE")
            if key[-1] == 'finished':
                d.callback(None)
        consumer = yield self.master.mq.startConsuming(
            buildEvent,
            ('builds', str(self.builddict['buildid']), None))

        yield d  # wait for event
        consumer.stopConsuming()
        defer.returnValue(self)  # callers expect result=self

    @defer.inlineCallbacks
    def remote_getResults(self):
        buildid = self.builddict['buildid']
        builddict = yield self.master.data.get(('builds', buildid))
        defer.returnValue(builddict['results'])

    @defer.inlineCallbacks
    def remote_getText(self):
        buildid = self.builddict['buildid']
        builddict = yield self.master.data.get(('builds', buildid))
        defer.returnValue([builddict['state_string']])


class Try_Userpass_Perspective(pbutil.NewCredPerspective):

    def __init__(self, scheduler, username):
        self.scheduler = scheduler
        self.username = username

    @defer.inlineCallbacks
    def perspective_try(self, branch, revision, patch, repository, project,
                        builderNames, who="", comment="", properties=None):
        log.msg("user %s requesting build on builders %s" % (self.username,
                                                             builderNames))
        if properties is None:
            properties = {}
        # build the intersection of the request and our configured list
        builderNames = self.scheduler.filterBuilderList(builderNames)
        if not builderNames:
            return

        reason = u"'try' job"

        if who:
            reason += u" by user %s" % ascii2unicode(who)

        if comment:
            reason += u" (%s)" % ascii2unicode(comment)

        sourcestamp = dict(
            branch=branch, revision=revision, repository=repository,
            project=project, patch_level=patch[0], patch_body=patch[1],
            patch_subdir='', patch_author=who or '',
            patch_comment=comment or '', codebase='',
        )           # note: no way to specify patch subdir - #1769

        requested_props = Properties()
        requested_props.update(properties, "try build")
        (bsid, brids) = yield self.scheduler.addBuildsetForSourceStamps(
            sourcestamps=[sourcestamp], reason=reason,
            properties=requested_props, builderNames=builderNames)

        # return a remotely-usable BuildSetStatus object
        bss = RemoteBuildSetStatus(self.scheduler.master, bsid, brids)
        defer.returnValue(bss)

    def perspective_getAvailableBuilderNames(self):
        # Return a list of builder names that are configured
        # for the try service
        # This is mostly intended for integrating try services
        # into other applications
        return self.scheduler.listBuilderNames()


class Try_Userpass(TryBase):
    compare_attrs = ('name', 'builderNames', 'port', 'userpass', 'properties')

    def __init__(self, name, builderNames, port, userpass, **kwargs):
        TryBase.__init__(self, name, builderNames, **kwargs)
        self.port = port
        self.userpass = userpass
        self.registrations = []

    @defer.inlineCallbacks
    def activate(self):
        yield TryBase.activate(self)

        if not self.enabled:
            return

        # register each user/passwd with the pbmanager
        def factory(mind, username):
            return Try_Userpass_Perspective(self, username)
        for user, passwd in self.userpass:
            self.registrations.append(
                self.master.pbmanager.register(
                    self.port, user, passwd, factory))

    @defer.inlineCallbacks
    def deactivate(self):
        yield TryBase.deactivate(self)

        if not self.enabled:
            return

        yield defer.gatherResults(
            [reg.unregister() for reg in self.registrations])
