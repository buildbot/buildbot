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
from email import charset
from email.header import Header
from email.message import Message
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate
from email.utils import parseaddr
from io import BytesIO

from twisted.internet import defer
from twisted.internet import reactor
from twisted.python import log as twlog
from zope.interface import implementer

from buildbot import config
from buildbot import interfaces
from buildbot import util
from buildbot.process.properties import Properties
from buildbot.process.results import Results
from buildbot.reporters.notifier import ENCODING
from buildbot.reporters.notifier import NotifierBase
from buildbot.util import ssl
from buildbot.util import unicode2bytes

# this incantation teaches email to output utf-8 using 7- or 8-bit encoding,
# although it has no effect before python-2.7.
# needs to match notifier.ENCODING
charset.add_charset(ENCODING, charset.SHORTEST, None, ENCODING)

try:
    from twisted.mail.smtp import ESMTPSenderFactory
    [ESMTPSenderFactory]  # for pyflakes
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


@implementer(interfaces.IEmailLookup)
class Domain(util.ComparableMixin):
    compare_attrs = ("domain")

    def __init__(self, domain):
        assert "@" not in domain
        self.domain = domain

    def getAddress(self, name):
        """If name is already an email address, pass it through."""
        if '@' in name:
            return name
        return name + "@" + self.domain


@implementer(interfaces.IEmailSender)
class MailNotifier(NotifierBase):
    secrets = ["smtpUser", "smtpPassword"]

    def checkConfig(self, fromaddr, mode=("failing", "passing", "warnings"),
                    tags=None, builders=None, addLogs=False,
                    relayhost="localhost", buildSetSummary=False,
                    subject="Buildbot %(result)s in %(title)s on %(builder)s",
                    lookup=None, extraRecipients=None,
                    sendToInterestedUsers=True,
                    messageFormatter=None, extraHeaders=None,
                    addPatch=True, useTls=False, useSmtps=False,
                    smtpUser=None, smtpPassword=None, smtpPort=25,
                    schedulers=None, branches=None,
                    watchedWorkers='all', messageFormatterMissingWorker=None,
                    dumpMailsToLog=False):
        if ESMTPSenderFactory is None:
            config.error("twisted-mail is not installed - cannot "
                         "send mail")

        super(MailNotifier, self).checkConfig(
            mode=mode, tags=tags, builders=builders,
            buildSetSummary=buildSetSummary, messageFormatter=messageFormatter,
            subject=subject, addLogs=addLogs, addPatch=addPatch,
            schedulers=schedulers, branches=branches,
            watchedWorkers=watchedWorkers, messageFormatterMissingWorker=messageFormatterMissingWorker)

        if extraRecipients is None:
            extraRecipients = []

        if not isinstance(extraRecipients, (list, tuple)):
            config.error("extraRecipients must be a list or tuple")
        else:
            for r in extraRecipients:
                if not isinstance(r, str) or not VALID_EMAIL.search(r):
                    config.error(
                        "extra recipient {} is not a valid email".format(r))

        if lookup is not None:
            if not isinstance(lookup, str):
                assert interfaces.IEmailLookup.providedBy(lookup)

        if extraHeaders:
            if not isinstance(extraHeaders, dict):
                config.error("extraHeaders must be a dictionary")

        if useSmtps:
            ssl.ensureHasSSL(self.__class__.__name__)

    def reconfigService(self, fromaddr, mode=("failing", "passing", "warnings"),
                        tags=None, builders=None, addLogs=False,
                        relayhost="localhost", buildSetSummary=False,
                        subject="Buildbot %(result)s in %(title)s on %(builder)s",
                        lookup=None, extraRecipients=None,
                        sendToInterestedUsers=True,
                        messageFormatter=None, extraHeaders=None,
                        addPatch=True, useTls=False, useSmtps=False,
                        smtpUser=None, smtpPassword=None, smtpPort=25,
                        schedulers=None, branches=None,
                        watchedWorkers='all', messageFormatterMissingWorker=None,
                        dumpMailsToLog=False):

        super(MailNotifier, self).reconfigService(
            mode=mode, tags=tags, builders=builders,
            buildSetSummary=buildSetSummary, messageFormatter=messageFormatter,
            subject=subject, addLogs=addLogs, addPatch=addPatch,
            schedulers=schedulers, branches=branches,
            watchedWorkers=watchedWorkers, messageFormatterMissingWorker=messageFormatterMissingWorker)
        if extraRecipients is None:
            extraRecipients = []
        self.extraRecipients = extraRecipients
        self.sendToInterestedUsers = sendToInterestedUsers
        self.fromaddr = fromaddr
        self.relayhost = relayhost
        if lookup is not None:
            if isinstance(lookup, str):
                lookup = Domain(str(lookup))
        self.lookup = lookup
        self.extraHeaders = extraHeaders
        self.useTls = useTls
        self.useSmtps = useSmtps
        self.smtpUser = smtpUser
        self.smtpPassword = smtpPassword
        self.smtpPort = smtpPort
        self.dumpMailsToLog = dumpMailsToLog

    def patch_to_attachment(self, patch, index):
        # patches are specifically converted to unicode before entering the db
        a = MIMEText(patch['body'].encode(ENCODING), _charset=ENCODING)
        a.add_header('Content-Disposition', "attachment",
                     filename="source patch " + str(index))
        return a

    @defer.inlineCallbacks
    def createEmail(self, msgdict, builderName, title, results, builds=None,
                    patches=None, logs=None):
        text = msgdict['body']
        type = msgdict['type']
        if msgdict.get('subject') is not None:
            subject = msgdict['subject']
        else:
            subject = self.subject % {'result': Results[results],
                                      'projectName': title,
                                      'title': title,
                                      'builder': builderName}

        assert '\n' not in subject, \
            "Subject cannot contain newlines"

        assert type in ('plain', 'html'), \
            "'{}' message type must be 'plain' or 'html'.".format(type)

        if patches or logs:
            m = MIMEMultipart()
            txt = MIMEText(text, type, ENCODING)
            m.attach(txt)
        else:
            m = Message()
            m.set_payload(text, ENCODING)
            m.set_type("text/{}".format(type))

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
                name = "{}.{}".format(log['stepname'],
                                      log['name'])
                if (self._shouldAttachLog(log['name']) or
                        self._shouldAttachLog(name)):
                    # Use distinct filenames for the e-mail summary
                    if self.buildSetSummary:
                        filename = "{}.{}".format(log['buildername'],
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
            if builds is not None and len(builds) == 1:
                props = Properties.fromDict(builds[0]['properties'])
                props.master = self.master
                extraHeaders = yield props.render(extraHeaders)

            for k, v in extraHeaders.items():
                if k in m:
                    twlog.msg("Warning: Got header " + k +
                              " in self.extraHeaders "
                              "but it already exists in the Message - "
                              "not adding it.")
                m[k] = v
        return m

    @defer.inlineCallbacks
    def sendMessage(self, body, subject=None, type='plain', builderName=None,
                    results=None, builds=None, users=None,
                    patches=None, logs=None, worker=None):
        body = unicode2bytes(body)
        msgdict = {'body': body, 'subject': subject, 'type': type}

        # ensure message body ends with double carriage return
        if not body.endswith(b"\n\n"):
            msgdict['body'] = body + b'\n\n'

        m = yield self.createEmail(msgdict, builderName, self.master.config.title,
                                   results, builds, patches, logs)

        # now, who is this message going to?
        if worker is None:
            recipients = yield self.findInterrestedUsersEmails(list(users))
            all_recipients = self.processRecipients(recipients, m)
        else:
            all_recipients = list(users)
        yield self.sendMail(m, all_recipients)

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
                    twlog.msg("INVALID EMAIL: {}".format(r))

        return recipients

    def formatAddress(self, addr):
        r = parseaddr(addr)
        if not r[0]:
            return r[1]
        return "\"%s\" <%s>" % (Header(r[0], 'utf-8').encode(), r[1])

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

        m['To'] = ", ".join([self.formatAddress(addr) for addr in sorted(to_recipients)])
        if cc_recipients:
            m['CC'] = ", ".join([self.formatAddress(addr) for addr in sorted(cc_recipients)])

        return list(to_recipients | cc_recipients)

    def sendMail(self, m, recipients):
        s = m.as_string()
        twlog.msg("sending mail ({} bytes) to".format(len(s)), recipients)
        if self.dumpMailsToLog:  # pragma: no cover
            twlog.msg("mail data:\n{0}".format(s))

        result = defer.Deferred()

        useAuth = self.smtpUser and self.smtpPassword

        s = unicode2bytes(s)
        recipients = [parseaddr(r)[1] for r in recipients]
        sender_factory = ESMTPSenderFactory(
            unicode2bytes(self.smtpUser), unicode2bytes(self.smtpPassword),
            parseaddr(self.fromaddr)[1], recipients, BytesIO(s),
            result, requireTransportSecurity=self.useTls,
            requireAuthentication=useAuth)

        if self.useSmtps:
            reactor.connectSSL(self.relayhost, self.smtpPort,
                               sender_factory, ssl.ClientContextFactory())
        else:
            reactor.connectTCP(self.relayhost, self.smtpPort, sender_factory)

        return result

    def isWorkerMessageNeeded(self, worker):
        return super(MailNotifier, self).isWorkerMessageNeeded(worker) \
               and worker['notify']
