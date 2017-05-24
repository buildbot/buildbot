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
"""
Push events to Gerrit
"""

from __future__ import absolute_import
from __future__ import print_function
from future.builtins import range
from future.utils import iteritems

import time
import warnings
from distutils.version import LooseVersion

from twisted.internet import defer
from twisted.internet import reactor
from twisted.internet.protocol import ProcessProtocol
from twisted.python import log

from buildbot.process.results import EXCEPTION
from buildbot.process.results import FAILURE
from buildbot.process.results import RETRY
from buildbot.process.results import SUCCESS
from buildbot.process.results import WARNINGS
from buildbot.process.results import Results
from buildbot.reporters import utils
from buildbot.util import bytes2NativeString
from buildbot.util import service

# Cache the version that the gerrit server is running for this many seconds
GERRIT_VERSION_CACHE_TIMEOUT = 600

GERRIT_LABEL_VERIFIED = 'Verified'
GERRIT_LABEL_REVIEWED = 'Code-Review'


def makeReviewResult(message, *labels):
    """
    helper to produce a review result
    """
    return dict(message=message, labels=dict(labels))


def _handleLegacyResult(result):
    """
    make sure the result is backward compatible
    """
    if not isinstance(result, dict):
        warnings.warn('The Gerrit status callback uses the old way to '
                      'communicate results.  The outcome might be not what is '
                      'expected.')
        message, verified, reviewed = result
        result = makeReviewResult(message,
                                  (GERRIT_LABEL_VERIFIED, verified),
                                  (GERRIT_LABEL_REVIEWED, reviewed))
    return result


def _old_add_label(label, value):
    if label == GERRIT_LABEL_VERIFIED:
        return ["--verified %d" % int(value)]
    elif label == GERRIT_LABEL_REVIEWED:
        return ["--code-review %d" % int(value)]
    warnings.warn('Gerrit older than 2.6 does not support custom labels. '
                  'Setting %s is ignored.' % label)
    return []


def _new_add_label(label, value):
    return ["--label %s=%d" % (label, int(value))]


def defaultReviewCB(builderName, build, result, master, arg):
    if result == RETRY:
        return makeReviewResult(None)

    message = "Buildbot finished compiling your patchset\n"
    message += "on configuration: %s\n" % builderName
    message += "The result is: %s\n" % Results[result].upper()

    return makeReviewResult(message,
                            (GERRIT_LABEL_VERIFIED, result == SUCCESS or -1))


def defaultSummaryCB(buildInfoList, results, master, arg):
    success = False
    failure = False

    msgs = []

    for buildInfo in buildInfoList:
        msg = "Builder %(name)s %(resultText)s (%(text)s)" % buildInfo
        link = buildInfo.get('url', None)
        if link:
            msg += " - " + link
        else:
            msg += "."
        msgs.append(msg)

        if buildInfo['result'] == SUCCESS:  # pylint: disable=simplifiable-if-statement
            success = True
        else:
            failure = True

    if success and not failure:
        verified = 1
    else:
        verified = -1

    return makeReviewResult('\n\n'.join(msgs), (GERRIT_LABEL_VERIFIED, verified))


# These are just sentinel values for GerritStatusPush.__init__ args
class DEFAULT_REVIEW(object):
    pass


class DEFAULT_SUMMARY(object):
    pass


class GerritStatusPush(service.BuildbotService):

    """Event streamer to a gerrit ssh server."""
    name = "GerritStatusPush"
    gerrit_server = None
    gerrit_username = None
    gerrit_port = None
    gerrit_version_time = None
    gerrit_version = None
    gerrit_identity_file = None
    reviewCB = None
    reviewArg = None
    startCB = None
    startArg = None
    summaryCB = None
    summaryArg = None
    _gerrit_notify = None

    def reconfigService(self, server, username, reviewCB=DEFAULT_REVIEW,
                        startCB=None, port=29418, reviewArg=None,
                        startArg=None, summaryCB=DEFAULT_SUMMARY, summaryArg=None,
                        identity_file=None, builders=None, notify=None):

        # If neither reviewCB nor summaryCB were specified, default to sending
        # out "summary" reviews. But if we were given a reviewCB and only a
        # reviewCB, disable the "summary" reviews, so we don't send out both
        # by default.
        if reviewCB is DEFAULT_REVIEW and summaryCB is DEFAULT_SUMMARY:
            reviewCB = None
            summaryCB = defaultSummaryCB
        if reviewCB is DEFAULT_REVIEW:
            reviewCB = None
        if summaryCB is DEFAULT_SUMMARY:
            summaryCB = None
        # Parameters.
        self.gerrit_server = server
        self.gerrit_username = username
        self.gerrit_port = port
        self.gerrit_version = None
        self.gerrit_version_time = 0
        self.gerrit_identity_file = identity_file
        self.reviewCB = reviewCB
        self.reviewArg = reviewArg
        self.startCB = startCB
        self.startArg = startArg
        self.summaryCB = summaryCB
        self.summaryArg = summaryArg
        self.builders = builders
        self._gerrit_notify = notify

    def _gerritCmd(self, *args):
        '''Construct a command as a list of strings suitable for
        :func:`subprocess.call`.
        '''
        if self.gerrit_identity_file is not None:
            options = ['-i', self.gerrit_identity_file]
        else:
            options = []
        return ['ssh'] + options + [
            '@'.join((self.gerrit_username, self.gerrit_server)),
            '-p', str(self.gerrit_port),
            'gerrit'
        ] + list(args)

    class VersionPP(ProcessProtocol):

        def __init__(self, func):
            self.func = func
            self.gerrit_version = None

        def outReceived(self, data):
            vstr = b"gerrit version "
            if not data.startswith(vstr):
                log.msg(b"Error: Cannot interpret gerrit version info: " + data)
                return
            vers = data[len(vstr):].strip()
            log.msg(b"gerrit version: " + vers)
            self.gerrit_version = LooseVersion(bytes2NativeString(vers))

        def errReceived(self, data):
            log.msg(b"gerriterr: " + data)

        def processEnded(self, status_object):
            if status_object.value.exitCode:
                log.msg("gerrit version status: ERROR:", status_object)
                return
            if self.gerrit_version:
                self.func(self.gerrit_version)

    def getCachedVersion(self):
        if self.gerrit_version is None:
            return None
        if time.time() - self.gerrit_version_time > GERRIT_VERSION_CACHE_TIMEOUT:
            # cached version has expired
            self.gerrit_version = None
        return self.gerrit_version

    def processVersion(self, gerrit_version, func):
        self.gerrit_version = gerrit_version
        self.gerrit_version_time = time.time()
        func()

    def callWithVersion(self, func):
        command = self._gerritCmd("version")

        def callback(gerrit_version):
            return self.processVersion(gerrit_version, func)

        self.spawnProcess(self.VersionPP(callback), command[0], command, env=None)

    class LocalPP(ProcessProtocol):

        def __init__(self, status):
            self.status = status

        def outReceived(self, data):
            log.msg("gerritout:", data)

        def errReceived(self, data):
            log.msg("gerriterr:", data)

        def processEnded(self, status_object):
            if status_object.value.exitCode:
                log.msg("gerrit status: ERROR:", status_object)
            else:
                log.msg("gerrit status: OK")

    @defer.inlineCallbacks
    def startService(self):
        yield service.BuildbotService.startService(self)
        startConsuming = self.master.mq.startConsuming
        self._buildsetCompleteConsumer = yield startConsuming(
            self.buildsetComplete,
            ('buildsets', None, 'complete'))

        self._buildCompleteConsumer = yield startConsuming(
            self.buildComplete,
            ('builds', None, 'finished'))

        self._buildStartedConsumer = yield startConsuming(
            self.buildStarted,
            ('builds', None, 'new'))

    def stopService(self):
        self._buildsetCompleteConsumer.stopConsuming()
        self._buildCompleteConsumer.stopConsuming()
        self._buildStartedConsumer.stopConsuming()

    @defer.inlineCallbacks
    def buildStarted(self, key, build):
        if self.startCB is None:
            return
        yield self.getBuildDetails(build)
        if self.isBuildReported(build):
            result = yield self.startCB(build['builder']['name'], build, self.startArg)
            self.sendCodeReviews(build, result)

    @defer.inlineCallbacks
    def buildComplete(self, key, build):
        if self.reviewCB is None:
            return
        yield self.getBuildDetails(build)
        if self.isBuildReported(build):
            result = yield self.reviewCB(build['builder']['name'], build, build['results'],
                                         self.master, self.reviewArg)
            result = _handleLegacyResult(result)
            self.sendCodeReviews(build, result)

    @defer.inlineCallbacks
    def getBuildDetails(self, build):
        br = yield self.master.data.get(("buildrequests", build['buildrequestid']))
        buildset = yield self.master.data.get(("buildsets", br['buildsetid']))
        yield utils.getDetailsForBuilds(self.master, buildset, [build], wantProperties=True)

    def isBuildReported(self, build):
        return self.builders is None or build['builder']['name'] in self.builders

    @defer.inlineCallbacks
    def buildsetComplete(self, key, msg):
        if not self.summaryCB:
            return
        bsid = msg['bsid']
        res = yield utils.getDetailsForBuildset(
            self.master, bsid, wantProperties=True)
        builds = res['builds']
        buildset = res['buildset']
        self.sendBuildSetSummary(buildset, builds)

    @defer.inlineCallbacks
    def sendBuildSetSummary(self, buildset, builds):
        builds = [build for build in builds if self.isBuildReported(build)]
        if builds and self.summaryCB:
            def getBuildInfo(build):
                result = build['results']
                resultText = {
                    SUCCESS: "succeeded",
                    FAILURE: "failed",
                    WARNINGS: "completed with warnings",
                    EXCEPTION: "encountered an exception",
                }.get(result, "completed with unknown result %d" % result)

                return {'name': build['builder']['name'],
                        'result': result,
                        'resultText': resultText,
                        'text': build['state_string'],
                        'url': utils.getURLForBuild(self.master, build['builder']['builderid'],
                                                    build['number']),
                        'build': build
                        }
            buildInfoList = sorted(
                [getBuildInfo(build) for build in builds], key=lambda bi: bi['name'])

            result = yield self.summaryCB(buildInfoList,
                                          Results[buildset['results']],
                                          self.master,
                                          self.summaryArg)

            result = _handleLegacyResult(result)
            self.sendCodeReviews(builds[0], result)

    def sendCodeReviews(self, build, result):
        message = result.get('message', None)
        if message is None:
            return

        def getProperty(build, name):
            return build['properties'].get(name, [None])[0]
        # Gerrit + Repo
        downloads = getProperty(build, "repo_downloads")
        downloaded = getProperty(build, "repo_downloaded")
        if downloads is not None and downloaded is not None:
            downloaded = downloaded.split(" ")
            if downloads and 2 * len(downloads) == len(downloaded):
                for i in range(0, len(downloads)):
                    try:
                        project, change1 = downloads[i].split(" ")
                    except ValueError:
                        return  # something is wrong, abort
                    change2 = downloaded[2 * i]
                    revision = downloaded[2 * i + 1]
                    if change1 == change2:
                        self.sendCodeReview(project, revision, result)
                    else:
                        return  # something is wrong, abort
            return

        # Gerrit + Git
        # used only to verify Gerrit source
        if getProperty(build, "event.change.id") is not None:
            project = getProperty(build, "event.change.project")
            codebase = getProperty(build, "codebase")
            revision = getProperty(
                build, "got_revision") or getProperty(build, "revision")

            if isinstance(revision, dict):
                # in case of the revision is a codebase revision, we just take
                # the revisionfor current codebase
                if codebase is not None:
                    revision = revision[codebase]
                else:
                    revision = None

            if project is not None and revision is not None:
                self.sendCodeReview(project, revision, result)
                return

    def sendCodeReview(self, project, revision, result):
        gerrit_version = self.getCachedVersion()
        if gerrit_version is None:
            self.callWithVersion(
                lambda: self.sendCodeReview(project, revision, result))
            return

        command = self._gerritCmd("review", "--project %s" % (project,))

        if self._gerrit_notify is not None:
            command.append('--notify %s' % str(self._gerrit_notify))

        message = result.get('message', None)
        if message:
            command.append("--message '%s'" % message.replace("'", "\""))

        labels = result.get('labels', None)
        if labels:
            assert gerrit_version
            if gerrit_version < LooseVersion("2.6"):
                add_label = _old_add_label
            else:
                add_label = _new_add_label

            for label, value in iteritems(labels):
                command.extend(add_label(label, value))

        command.append(revision)
        command = [str(s) for s in command]
        self.spawnProcess(self.LocalPP(self), command[0], command, env=None)

    def spawnProcess(self, *arg, **kw):
        reactor.spawnProcess(*arg, **kw)
