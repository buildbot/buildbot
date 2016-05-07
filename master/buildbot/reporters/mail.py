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
import re
# this incantation teaches email to output utf-8 using 7- or 8-bit encoding,
# although it has no effect before python-2.7.
from email import charset
from email.message import Message
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate
from StringIO import StringIO

from future.utils import iteritems
from twisted.internet import defer
from twisted.internet import reactor
from twisted.python import log as twlog
from zope.interface import implements

from buildbot import config
from buildbot import interfaces
from buildbot import util
from buildbot.process.properties import Properties
from buildbot.process.results import CANCELLED
from buildbot.process.results import EXCEPTION
from buildbot.process.results import FAILURE
from buildbot.process.results import SUCCESS
from buildbot.process.results import WARNINGS
from buildbot.process.results import Results
from buildbot.reporters import utils
from buildbot.reporters.message import MessageFormatter as DefaultMessageFormatter
from buildbot.util import service

charset.add_charset('utf-8', charset.SHORTEST, None, 'utf-8')

try:
    from twisted.mail.smtp import ESMTPSenderFactory
    ESMTPSenderFactory = ESMTPSenderFactory  # for pyflakes
except ImportError:
    ESMTPSenderFactory = None


# Email parsing can be complex. We try to take a very liberal
# approach. The local part of an email address matches ANY non
# whitespace character. Rather allow a malformed email address than
# croaking on a valid (the matching of domains should be correct
# though; requiring the domain to not be a top level domain). With
# these regular expressions, we can match the following:
#
#    full.name@example.net
#    Full Name <full.name@example.net>
#    <full.name@example.net>
VALID_EMAIL_ADDR = r"(?:\S+@[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)+\.?)"
VALID_EMAIL = re.compile(r"^(?:%s|(.+\s+)?<%s>\s*)$" %
                         ((VALID_EMAIL_ADDR,) * 2))
VALID_EMAIL_ADDR = re.compile(VALID_EMAIL_ADDR)

ENCODING = 'utf8'


class Domain(util.ComparableMixin):
    implements(interfaces.IEmailLookup)
    compare_attrs = ("domain")

    def __init__(self, domain):
        assert "@" not in domain
        self.domain = domain

    def getAddress(self, name):
        """If name is already an email address, pass it through."""
        if '@' in name:
            return name
        return name + "@" + self.domain


class MailNotifier(service.BuildbotService):

    implements(interfaces.IEmailSender)

    possible_modes = ("change", "failing", "passing", "problem", "warnings",
                      "exception", "cancelled")

    def computeShortcutModes(self, mode):
        if isinstance(mode, basestring):
            if mode == "all":
                mode = ("failing", "passing", "warnings",
                        "exception", "cancelled")
            elif mode == "warnings":
                mode = ("failing", "warnings")
            else:
                mode = (mode,)
        return mode

    def checkConfig(self, fromaddr, mode=("failing", "passing", "warnings"),
                    tags=None, builders=None, addLogs=False,
                    relayhost="localhost", buildSetSummary=False,
                    subject="buildbot %(result)s in %(title)s on %(builder)s",
                    lookup=None, extraRecipients=None,
                    sendToInterestedUsers=True,
                    messageFormatter=None, extraHeaders=None,
                    addPatch=True, useTls=False,
                    smtpUser=None, smtpPassword=None, smtpPort=25,
                    name=None
                    ):
        if ESMTPSenderFactory is None:
            config.error("twisted-mail is not installed - cannot "
                         "send mail")

        if extraRecipients is None:
            extraRecipients = []

        if not isinstance(extraRecipients, (list, tuple)):
            config.error("extraRecipients must be a list or tuple")
        else:
            for r in extraRecipients:
                if not isinstance(r, str) or not VALID_EMAIL.search(r):
                    config.error(
                        "extra recipient %r is not a valid email" % (r,))

        for m in self.computeShortcutModes(mode):
            if m not in self.possible_modes:
                if m == "all":
                    config.error(
                        "mode 'all' is not valid in an iterator and must be passed in as a separate string")
                else:
                    config.error(
                        "mode %s is not a valid mode" % (m,))

        if name is None:
            self.name = "MailNotifier"
            if tags is not None:
                self.name += "_tags_" + "+".join(tags)
            if builders is not None:
                self.name += "_builders_" + "+".join(builders)

        if '\n' in subject:
            config.error(
                'Newlines are not allowed in email subjects')

        if lookup is not None:
            if not isinstance(lookup, basestring):
                assert interfaces.IEmailLookup.providedBy(lookup)

        if extraHeaders:
            if not isinstance(extraHeaders, dict):
                config.error("extraHeaders must be a dictionary")

        # you should either limit on builders or tags, not both
        if builders is not None and tags is not None:
            config.error(
                "Please specify only builders or tags to include - " +
                "not both.")

    def reconfigService(self, fromaddr, mode=("failing", "passing", "warnings"),
                        tags=None, builders=None, addLogs=False,
                        relayhost="localhost", buildSetSummary=False,
                        subject="buildbot %(result)s in %(title)s on %(builder)s",
                        lookup=None, extraRecipients=None,
                        sendToInterestedUsers=True,
                        messageFormatter=None, extraHeaders=None,
                        addPatch=True, useTls=False,
                        smtpUser=None, smtpPassword=None, smtpPort=25,
                        name=None
                        ):

        if extraRecipients is None:
            extraRecipients = []

        self.extraRecipients = extraRecipients
        self.sendToInterestedUsers = sendToInterestedUsers
        self.fromaddr = fromaddr
        self.mode = self.computeShortcutModes(mode)
        self.tags = tags
        self.builders = builders
        self.addLogs = addLogs
        self.relayhost = relayhost
        self.subject = subject
        if lookup is not None:
            if isinstance(lookup, basestring):
                lookup = Domain(str(lookup))

        self.lookup = lookup
        if messageFormatter is None:
            messageFormatter = DefaultMessageFormatter()
        self.messageFormatter = messageFormatter
        self.extraHeaders = extraHeaders
        self.addPatch = addPatch
        self.useTls = useTls
        self.smtpUser = smtpUser
        self.smtpPassword = smtpPassword
        self.smtpPort = smtpPort
        self.buildSetSummary = buildSetSummary
        self._buildset_complete_consumer = None
        self.watched = []

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

    @defer.inlineCallbacks
    def stopService(self):
        yield service.BuildbotService.stopService(self)
        if self._buildsetCompleteConsumer is not None:
            yield self._buildsetCompleteConsumer.stopConsuming()
            self._buildsetCompleteConsumer = None
        if self._buildCompleteConsumer is not None:
            yield self._buildCompleteConsumer.stopConsuming()
            self._buildCompleteConsumer = None

    def wantPreviousBuild(self):
        return "change" in self.mode or "problem" in self.mode

    @defer.inlineCallbacks
    def buildsetComplete(self, key, msg):
        if not self.buildSetSummary:
            return
        bsid = msg['bsid']
        res = yield utils.getDetailsForBuildset(
            self.master, bsid,
            wantProperties=self.messageFormatter.wantProperties,
            wantSteps=self.messageFormatter.wantSteps,
            wantPreviousBuild=self.wantPreviousBuild())

        builds = res['builds']
        buildset = res['buildset']

        # only include builds for which isMailNeeded returns true
        builds = [build for build in builds if self.isMailNeeded(build)]
        if builds:
            self.buildMessage("(whole buildset)", builds, buildset['results'])

    @defer.inlineCallbacks
    def buildComplete(self, key, build):
        if self.buildSetSummary:
            return
        br = yield self.master.data.get(("buildrequests", build['buildrequestid']))
        buildset = yield self.master.data.get(("buildsets", br['buildsetid']))
        yield utils.getDetailsForBuilds(
            self.master, buildset, [build],
            wantProperties=self.messageFormatter.wantProperties,
            wantSteps=self.messageFormatter.wantSteps,
            wantPreviousBuild=self.wantPreviousBuild())
        # only include builds for which isMailNeeded returns true
        if self.isMailNeeded(build):
            self.buildMessage(
                build['builder']['name'], [build], build['results'])

    def matchesAnyTag(self, tags):
        return self.tags and any(tag for tag in self.tags if tag in tags)

    def isMailNeeded(self, build):
        # here is where we actually do something.
        builder = build['builder']
        results = build['results']
        if self.builders is not None and builder['name'] not in self.builders:
            return False  # ignore this build
        if self.tags is not None and \
                not self.matchesAnyTag(builder['tags']):
            return False  # ignore this build

        if "change" in self.mode:
            prev = build['prev_build']
            if prev and prev['results'] != results:
                return True
        if "failing" in self.mode and results == FAILURE:
            return True
        if "passing" in self.mode and results == SUCCESS:
            return True
        if "problem" in self.mode and results == FAILURE:
            prev = build['prev_build']
            if prev and prev['results'] != FAILURE:
                return True
        if "warnings" in self.mode and results == WARNINGS:
            return True
        if "exception" in self.mode and results == EXCEPTION:
            return True
        if "cancelled" in self.mode and results == CANCELLED:
            return True

        return False

    def patch_to_attachment(self, patch, index):
        # patches are specificaly converted to unicode before entering the db
        a = MIMEText(patch['body'].encode(ENCODING), _charset=ENCODING)
        a.add_header('Content-Disposition', "attachment",
                     filename="source patch " + str(index))
        return a

    @defer.inlineCallbacks
    def createEmail(self, msgdict, builderName, title, results, builds=None,
                    patches=None, logs=None):
        text = msgdict['body'].encode(ENCODING)
        type = msgdict['type']
        if 'subject' in msgdict:
            subject = msgdict['subject'].encode(ENCODING)
        else:
            subject = self.subject % {'result': Results[results],
                                      'projectName': title,
                                      'title': title,
                                      'builder': builderName,
                                      }

        assert '\n' not in subject, \
            "Subject cannot contain newlines"

        assert type in ('plain', 'html'), \
            "'%s' message type must be 'plain' or 'html'." % type

        if patches or logs:
            m = MIMEMultipart()
            txt = MIMEText(text, type, ENCODING)
            m.attach(txt)
        else:
            m = Message()
            m.set_payload(text, ENCODING)
            m.set_type("text/%s" % type)

        m['Date'] = formatdate(localtime=True)
        m['Subject'] = subject
        m['From'] = self.fromaddr
        # m['To'] is added later

        if patches:
            for (i, patch) in enumerate(patches):
                a = self.patch_to_attachment(patch, i)
                m.attach(a)
        if logs:
            for log in logs:
                name = "%s.%s" % (log['stepname'],
                                  log['name'])
                if (self._shouldAttachLog(log['name']) or
                        self._shouldAttachLog(name)):
                    # Use distinct filenames for the e-mail summary
                    if self.buildSetSummary:
                        filename = "%s.%s" % (log['buildername'],
                                              name)
                    else:
                        filename = name

                    text = log['content']['content']
                    a = MIMEText(text.encode(ENCODING),
                                 _charset=ENCODING)
                    a.add_header('Content-Disposition', "attachment",
                                 filename=filename)
                    m.attach(a)

        # @todo: is there a better way to do this?
        # Add any extra headers that were requested, doing WithProperties
        # interpolation if only one build was given
        if self.extraHeaders:
            extraHeaders = self.extraHeaders
            if len(builds) == 1:
                props = Properties.fromDict(builds[0]['properties'])
                extraHeaders = yield props.render(extraHeaders)

            for k, v in iteritems(extraHeaders):
                if k in m:
                    twlog.msg("Warning: Got header " + k +
                              " in self.extraHeaders "
                              "but it already exists in the Message - "
                              "not adding it.")
                m[k] = v
        defer.returnValue(m)

    @defer.inlineCallbacks
    def getLogsForBuild(self, build):
        all_logs = []
        steps = yield self.master.data.get(('builds', build['buildid'], "steps"))
        for step in steps:
            logs = yield self.master.data.get(("steps", step['stepid'], 'logs'))
            for l in logs:
                l['stepname'] = step['name']
                l['content'] = yield self.master.data.get(("logs", l['logid'], 'contents'))
                all_logs.append(l)
        defer.returnValue(all_logs)

    @defer.inlineCallbacks
    def buildMessage(self, name, builds, results):
        patches = []
        logs = []
        msgdict = {"body": ""}
        users = set()
        for build in builds:
            if self.addPatch:
                ss_list = build['buildset']['sourcestamps']

                for ss in ss_list:
                    if 'patch' in ss and ss['patch'] is not None:
                        patches.append(ss['patch'])
            if self.addLogs:
                build_logs = yield self.getLogsForBuild(build)
                logs.extend(build_logs)

            if 'prev_build' in build and build['prev_build'] is not None:
                previous_results = build['prev_build']['results']
            else:
                previous_results = None
            blamelist = yield utils.getResponsibleUsersForBuild(self.master, build['buildid'])
            build_msgdict = self.messageFormatter(self.mode, name, build['buildset'], build, self.master,
                                                  previous_results, blamelist)
            users.update(set(blamelist))
            msgdict['type'] = build_msgdict['type']
            msgdict['body'] += build_msgdict['body']
            if 'subject' in build_msgdict:
                msgdict['subject'] = build_msgdict['subject']
            # ensure msgbody ends with double cariage return
            if not msgdict['body'].endswith("\n\n"):
                msgdict['body'] += '\n\n'

        m = yield self.createEmail(msgdict, name, self.master.config.title,
                                   results, builds, patches, logs)

        # now, who is this message going to?
        recipients = yield self.findInterrestedUsersEmails(list(users))
        all_recipients = self.processRecipients(recipients, m)
        yield self.sendMessage(m, all_recipients)

    def _shouldAttachLog(self, logname):
        if isinstance(self.addLogs, bool):
            return self.addLogs
        return logname in self.addLogs

    @defer.inlineCallbacks
    def findInterrestedUsersEmails(self, users):
        recipients = set()
        if self.sendToInterestedUsers:
            if self.lookup:
                dl = []
                for u in users:
                    dl.append(defer.maybeDeferred(self.lookup.getAddress, u))
                users = yield defer.gatherResults(dl)

            for r in users:
                if r is None:  # getAddress didn't like this address
                    continue

                # Git can give emails like 'User' <user@foo.com>@foo.com so check
                # for two @ and chop the last
                if r.count('@') > 1:
                    r = r[:r.rindex('@')]

                if VALID_EMAIL.search(r):
                    recipients.add(r)
                else:
                    twlog.msg("INVALID EMAIL: %r" % r)

        defer.returnValue(recipients)

    def processRecipients(self, blamelist, m):
        to_recipients = set(blamelist)
        cc_recipients = set()

        # If we're sending to interested users put the extras in the
        # CC list so they can tell if they are also interested in the
        # change:
        if self.sendToInterestedUsers and to_recipients:
            cc_recipients.update(self.extraRecipients)
        else:
            to_recipients.update(self.extraRecipients)

        m['To'] = ", ".join(sorted(to_recipients))
        if cc_recipients:
            m['CC'] = ", ".join(sorted(cc_recipients))

        return list(to_recipients | cc_recipients)

    def sendmail(self, s, recipients):
        result = defer.Deferred()

        if self.smtpUser and self.smtpPassword:
            useAuth = True
        else:
            useAuth = False

        sender_factory = ESMTPSenderFactory(
            self.smtpUser, self.smtpPassword,
            self.fromaddr, recipients, StringIO(s),
            result, requireTransportSecurity=self.useTls,
            requireAuthentication=useAuth)

        reactor.connectTCP(self.relayhost, self.smtpPort, sender_factory)

        return result

    def sendMessage(self, m, recipients):
        s = m.as_string()
        twlog.msg("sending mail (%d bytes) to" % len(s), recipients)
        return self.sendmail(s, recipients)
