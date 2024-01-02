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

import time
import warnings

from packaging.version import parse as parse_version

from twisted.internet import defer
from twisted.internet import reactor
from twisted.internet.protocol import ProcessProtocol
from twisted.python import log
from zope.interface import implementer

from buildbot import config
from buildbot import interfaces
from buildbot.process.results import EXCEPTION
from buildbot.process.results import FAILURE
from buildbot.process.results import RETRY
from buildbot.process.results import SUCCESS
from buildbot.process.results import WARNINGS
from buildbot.process.results import Results
from buildbot.reporters import utils
from buildbot.reporters.base import ReporterBase
from buildbot.util import bytes2unicode
from buildbot.warnings import warn_deprecated

# Cache the version that the gerrit server is running for this many seconds
GERRIT_VERSION_CACHE_TIMEOUT = 600

GERRIT_LABEL_VERIFIED = 'Verified'
GERRIT_LABEL_REVIEWED = 'Code-Review'


def makeReviewResult(message, *labels):
    """
    helper to produce a review result
    """
    return {"message": message, "labels": dict(labels)}


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
        return [f"--verified {int(value)}"]
    elif label == GERRIT_LABEL_REVIEWED:
        return [f"--code-review {int(value)}"]
    warnings.warn('Gerrit older than 2.6 does not support custom labels. '
                  f'Setting {label} is ignored.')
    return []


def _new_add_label(label, value):
    return [f"--label {label}={int(value)}"]


def defaultReviewCB(builderName, build, result, master, arg):
    if result == RETRY:
        return makeReviewResult(None)

    message = "Buildbot finished compiling your patchset\n"
    message += f"on configuration: {builderName}\n"
    message += f"The result is: {Results[result].upper()}\n"

    return makeReviewResult(message,
                            (GERRIT_LABEL_VERIFIED, result == SUCCESS or -1))


def defaultSummaryCB(buildInfoList, results, master, arg):
    success = False
    failure = False

    msgs = []

    for buildInfo in buildInfoList:
        msg = f"Builder {buildInfo['name']} {buildInfo['resultText']} ({buildInfo['text']})"
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
class DEFAULT_REVIEW:
    pass


class DEFAULT_SUMMARY:
    pass


@defer.inlineCallbacks
def extract_project_revision(master, report):
    props = None
    if report["builds"]:
        props = report["builds"][0].get("properties", None)

    if props is None:
        props = yield master.data.get(("buildsets", report["buildset"]["bsid"], "properties"))

    def get_property(props, name):
        if props is None:
            return None
        return props.get(name, [None])[0]

    # Gerrit + Repo
    downloads = get_property(props, "repo_downloads")
    downloaded = get_property(props, "repo_downloaded")
    if downloads is not None and downloaded is not None:
        downloaded = downloaded.split(" ")
        if downloads and 2 * len(downloads) == len(downloaded):
            for i, download in enumerate(downloads):
                try:
                    project, change1 = download.split(" ")
                except ValueError:
                    return None, None  # something is wrong, abort
                change2 = downloaded[2 * i]
                revision = downloaded[2 * i + 1]
                if change1 == change2:
                    return project, revision
                else:
                    return None, None
        return None, None

    # Gerrit + Git
    # used only to verify Gerrit source
    if get_property(props, "event.change.id") is not None:
        project = get_property(props, "event.change.project")
        codebase = get_property(props, "codebase")
        revision = (
            get_property(props, "event.patchSet.revision") or
            get_property(props, "got_revision") or
            get_property(props, "revision")
        )

        if isinstance(revision, dict):
            # in case of the revision is a codebase revision, we just take
            # the revisionfor current codebase
            if codebase is not None:
                revision = revision[codebase]
            else:
                revision = None

        return project, revision

    return None, None


class GerritStatusGeneratorBase:

    def __init__(self, callback, callback_arg, builders, want_steps, want_logs):
        self.callback = callback
        self.callback_arg = callback_arg
        self.builders = builders
        self.want_steps = want_steps
        self.want_logs = want_logs

    def is_build_reported(self, build):
        return self.builders is None or build["builder"]["name"] in self.builders

    @defer.inlineCallbacks
    def get_build_details(self, master, build):
        br = yield master.data.get(("buildrequests", build["buildrequestid"]))
        buildset = yield master.data.get(("buildsets", br["buildsetid"]))
        yield utils.getDetailsForBuilds(
            master,
            buildset,
            [build],
            want_properties=True,
            want_steps=self.want_steps
        )


@implementer(interfaces.IReportGenerator)
class GerritBuildSetStatusGenerator(GerritStatusGeneratorBase):
    wanted_event_keys = [
        ("buildsets", None, "complete"),
    ]

    def check(self):
        pass

    @defer.inlineCallbacks
    def generate(self, master, reporter, key, message):
        bsid = message["bsid"]
        res = yield utils.getDetailsForBuildset(
            master,
            bsid,
            want_properties=True,
            want_steps=self.want_steps,
            want_logs=self.want_logs,
            want_logs_content=self.want_logs
        )

        builds = res["builds"]
        buildset = res["buildset"]

        builds = [build for build in builds if self.is_build_reported(build)]
        if not builds:
            return None

        def get_build_info(build):
            result = build["results"]
            resultText = {
                SUCCESS: "succeeded",
                FAILURE: "failed",
                WARNINGS: "completed with warnings",
                EXCEPTION: "encountered an exception",
            }.get(result, f"completed with unknown result {result}")

            return {
                "name": build["builder"]["name"],
                "result": result,
                "resultText": resultText,
                "text": build["state_string"],
                "url": utils.getURLForBuild(
                    master,
                    build["builder"]["builderid"],
                    build["number"]
                ),
                "build": build
            }

        build_info_list = sorted(
            [get_build_info(build) for build in builds], key=lambda bi: bi["name"]
        )

        result = yield self.callback(
            build_info_list,
            Results[buildset["results"]],
            master,
            self.callback_arg
        )

        result = _handleLegacyResult(result)

        return {
            "body": result.get("message", None),
            "extra_info": {
                "labels": result.get("labels"),
            },
            "builds": [builds[0]],
            "buildset": buildset,
        }


@implementer(interfaces.IReportGenerator)
class GerritBuildStartStatusGenerator(GerritStatusGeneratorBase):
    wanted_event_keys = [
        ("builds", None, "new"),
    ]

    def check(self):
        pass

    @defer.inlineCallbacks
    def generate(self, master, reporter, key, message):
        build = message
        yield self.get_build_details(master, build)
        if not self.is_build_reported(build):
            return None

        result = yield self.callback(build["builder"]["name"], build, self.callback_arg)

        result = _handleLegacyResult(result)

        return {
            "body": result.get("message", None),
            "extra_info": {
                "labels": result.get("labels"),
            },
            "builds": [build],
            "buildset": build["buildset"],
        }


@implementer(interfaces.IReportGenerator)
class GerritBuildEndStatusGenerator(GerritStatusGeneratorBase):
    wanted_event_keys = [
        ('builds', None, 'finished'),
    ]

    def check(self):
        pass

    @defer.inlineCallbacks
    def generate(self, master, reporter, key, message):
        build = message
        yield self.get_build_details(master, build)
        if not self.is_build_reported(build):
            return None

        result = yield self.callback(
            build['builder']['name'],
            build,
            build['results'],
            master,
            self.callback_arg
        )

        result = _handleLegacyResult(result)

        return {
            "body": result.get("message", None),
            "extra_info": {
                "labels": result.get("labels"),
            },
            "builds": [build],
            "buildset": build["buildset"],
        }


class GerritStatusPush(ReporterBase):

    """Event streamer to a gerrit ssh server."""
    name = "GerritStatusPush"
    gerrit_server = None
    gerrit_username = None
    gerrit_port = None
    gerrit_version_time = None
    gerrit_version = None
    gerrit_identity_file = None
    _gerrit_notify = None

    def checkConfig(
        self,
        server,
        username,
        reviewCB=DEFAULT_REVIEW,
        startCB=None,
        port=29418,
        reviewArg=None,
        startArg=None,
        summaryCB=DEFAULT_SUMMARY,
        summaryArg=None,
        identity_file=None,
        builders=None,
        notify=None,
        wantSteps=False,
        wantLogs=False,
        generators=None,
        **kwargs
    ):
        old_arg_names = {
            "reviewCB": reviewCB is not DEFAULT_REVIEW,
            "startCB": startCB is not None,
            "reviewArg": reviewArg is not None,
            "startArg": startArg is not None,
            "summaryCB": summaryCB is not DEFAULT_SUMMARY,
            "summaryArg": summaryArg is not None,
            "builders": builders is not None,
            "wantSteps": wantSteps is not False,
            "wantLogs": wantLogs is not False,
        }

        passed_old_arg_names = [k for k, v in old_arg_names.items() if v]

        if passed_old_arg_names:
            old_arg_names_msg = ', '.join(passed_old_arg_names)
            if generators is not None:
                config.error("can't specify generators and deprecated GerritStatusPush "
                             f"arguments ({old_arg_names_msg}) at the same time")
            warn_deprecated(
                "3.11.0",
                f"The arguments {old_arg_names_msg} passed to {self.__class__.__name__} "
                "have been deprecated. Use generators instead"
            )

        if generators is None:
            generators = self._create_generators_from_old_args(
                reviewCB,
                startCB,
                reviewArg,
                startArg,
                summaryCB,
                summaryArg,
                builders,
                wantSteps,
                wantLogs
            )

        super().checkConfig(generators=generators, **kwargs)

    def reconfigService(
        self,
        server,
        username,
        reviewCB=DEFAULT_REVIEW,
        startCB=None,
        port=29418,
        reviewArg=None,
        startArg=None,
        summaryCB=DEFAULT_SUMMARY,
        summaryArg=None,
        identity_file=None,
        builders=None,
        notify=None,
        wantSteps=False,
        wantLogs=False,
        generators=None,
        **kwargs
    ):
        self.gerrit_server = server
        self.gerrit_username = username
        self.gerrit_port = port
        self.gerrit_version = None
        self.gerrit_version_time = 0
        self.gerrit_identity_file = identity_file
        self._gerrit_notify = notify

        if generators is None:
            generators = self._create_generators_from_old_args(
                reviewCB,
                startCB,
                reviewArg,
                startArg,
                summaryCB,
                summaryArg,
                builders,
                wantSteps,
                wantLogs
            )

        super().reconfigService(generators=generators, **kwargs)

    def _create_generators_from_old_args(
        self,
        reviewCB,
        startCB,
        reviewArg,
        startArg,
        summaryCB,
        summaryArg,
        builders,
        wantSteps,
        wantLogs
    ):
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

        generators = []

        if startCB is not None:
            generators.append(
                GerritBuildStartStatusGenerator(
                    callback=startCB,
                    callback_arg=startArg,
                    builders=builders,
                    want_steps=wantSteps,
                    want_logs=wantLogs
                )
            )

        if reviewCB is not None:
            generators.append(
                GerritBuildEndStatusGenerator(
                    callback=reviewCB,
                    callback_arg=reviewArg,
                    builders=builders,
                    want_steps=wantSteps,
                    want_logs=wantLogs
                )
            )

        if summaryCB is not None:
            generators.append(
                GerritBuildSetStatusGenerator(
                    callback=summaryCB,
                    callback_arg=summaryArg,
                    builders=builders,
                    want_steps=wantSteps,
                    want_logs=wantLogs
                )
            )

        return generators

    def _gerritCmd(self, *args):
        '''Construct a command as a list of strings suitable for
        :func:`subprocess.call`.
        '''
        if self.gerrit_identity_file is not None:
            options = ['-i', self.gerrit_identity_file]
        else:
            options = []
        return ['ssh', '-o', 'BatchMode=yes'] + options + [
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
            self.gerrit_version = parse_version(bytes2unicode(vers))

        def errReceived(self, data):
            log.msg(b"gerriterr: " + data)

        def processEnded(self, reason):
            if reason.value.exitCode:
                log.msg("gerrit version status: ERROR:", reason)
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

        def processEnded(self, reason):
            if reason.value.exitCode:
                log.msg("gerrit status: ERROR:", reason)
            else:
                log.msg("gerrit status: OK")

    @defer.inlineCallbacks
    def sendMessage(self, reports):
        report = reports[0]

        project, revision = yield extract_project_revision(self.master, report)

        if report["body"] is None or project is None or revision is None:
            return None

        labels = None
        extra_info = report.get("extra_info", None)
        if extra_info is not None:
            labels = extra_info.get("labels", None)

        if labels is None and report.get("builds", None):
            # At least one build
            success = False
            failure = False
            pending = False

            for build in report["builds"]:
                if build["results"] is None:
                    pending = True
                elif build["results"] == SUCCESS:
                    success = True
                else:
                    failure = True

            if failure:
                verified = -1
            elif pending:
                verified = 0
            elif success:
                verified = 1
            else:
                verified = -1

            labels = {GERRIT_LABEL_VERIFIED: verified}

        self.send_code_review(project, revision, report["body"], labels)
        return None

    def send_code_review(self, project, revision, message, labels):
        gerrit_version = self.getCachedVersion()
        if gerrit_version is None:
            self.callWithVersion(lambda: self.send_code_review(project, revision, message, labels))
            return

        assert gerrit_version
        command = self._gerritCmd("review", f"--project {project}")

        if gerrit_version >= parse_version("2.13"):
            command.append('--tag autogenerated:buildbot')

        if self._gerrit_notify is not None:
            command.append(f'--notify {str(self._gerrit_notify)}')

        if message:
            message = message.replace("'", "\"")
            command.append(f"--message '{message}'")

        if labels:
            if gerrit_version < parse_version("2.6"):
                add_label = _old_add_label
            else:
                add_label = _new_add_label

            for label, value in labels.items():
                command.extend(add_label(label, value))

        command.append(revision)
        command = [str(s) for s in command]
        self.spawnProcess(self.LocalPP(self), command[0], command, env=None)

    def spawnProcess(self, *arg, **kw):
        reactor.spawnProcess(*arg, **kw)
