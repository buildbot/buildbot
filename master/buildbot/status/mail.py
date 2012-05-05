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
import types
from email.Message import Message
from email.Utils import formatdate
from email.MIMEText import MIMEText
from email.MIMENonMultipart import MIMENonMultipart
from email.MIMEMultipart import MIMEMultipart
from StringIO import StringIO
import urllib

from zope.interface import implements
from twisted.internet import defer, reactor
from twisted.python import log as twlog

try:
    from twisted.mail.smtp import ESMTPSenderFactory
    ESMTPSenderFactory = ESMTPSenderFactory # for pyflakes
except ImportError:
    ESMTPSenderFactory = None

have_ssl = True
try:
    from twisted.internet import ssl
    from OpenSSL.SSL import SSLv3_METHOD
except ImportError:
    have_ssl = False

from buildbot import interfaces, util, config
from buildbot.process.users import users
from buildbot.status import base
from buildbot.status.results import FAILURE, SUCCESS, WARNINGS, Results

VALID_EMAIL = re.compile("[a-zA-Z0-9\.\_\%\-\+]+@[a-zA-Z0-9\.\_\%\-]+.[a-zA-Z]{2,6}")

ENCODING = 'utf8'
LOG_ENCODING = 'utf-8'

class Domain(util.ComparableMixin):
    implements(interfaces.IEmailLookup)
    compare_attrs = ["domain"]

    def __init__(self, domain):
        assert "@" not in domain
        self.domain = domain

    def getAddress(self, name):
        """If name is already an email address, pass it through."""
        if '@' in name:
            return name
        return name + "@" + self.domain


def defaultMessage(mode, name, build, results, master_status):
    """Generate a buildbot mail message and return a tuple of message text
        and type."""
    ss_list = build.getSourceStamps()
    
    prev = build.getPreviousBuild()

    text = ""
    if results == FAILURE:
        if "change" in mode and prev and prev.getResults() != results or \
               "problem" in mode and prev and prev.getResults() != FAILURE:
            text += "The Buildbot has detected a new failure"
        else:
            text += "The Buildbot has detected a failed build"
    elif results == WARNINGS:
        text += "The Buildbot has detected a problem in the build"
    elif results == SUCCESS:
        if "change" in mode and prev and prev.getResults() != results:
            text += "The Buildbot has detected a restored build"
        else:
            text += "The Buildbot has detected a passing build"

    projects = []
    if ss_list:
        for ss in ss_list:
            if ss.project and ss.project not in projects:
                projects.append(ss.project)
    if not projects:
        projects = [master_status.getTitle()]
    text += " on builder %s while building %s.\n" % (name, ', '.join(projects))

    if master_status.getURLForThing(build):
        text += "Full details are available at:\n %s\n" % master_status.getURLForThing(build)
    text += "\n"

    if master_status.getBuildbotURL():
        text += "Buildbot URL: %s\n\n" % urllib.quote(master_status.getBuildbotURL(), '/:')

    text += "Buildslave for this Build: %s\n\n" % build.getSlavename()
    text += "Build Reason: %s\n" % build.getReason()

    for ss in ss_list:
        source = ""
        if ss and ss.branch:
            source += "[branch %s] " % ss.branch
        if ss and ss.revision:
            source += str(ss.revision)
        else:
            source += "HEAD"
        if ss and ss.patch:
            source += " (plus patch)"

        discriminator = ""
        if ss.codebase:
            discriminator = " '%s'" % ss.codebase
        text += "Build Source Stamp%s: %s\n" % (discriminator, source)

    text += "Blamelist: %s\n" % ",".join(build.getResponsibleUsers())

    text += "\n"

    t = build.getText()
    if t:
        t = ": " + " ".join(t)
    else:
        t = ""

    if results == SUCCESS:
        text += "Build succeeded!\n"
    elif results == WARNINGS:
        text += "Build Had Warnings%s\n" % t
    else:
        text += "BUILD FAILED%s\n" % t

    text += "\n"
    text += "sincerely,\n"
    text += " -The Buildbot\n"
    text += "\n"
    return { 'body' : text, 'type' : 'plain' }

class MailNotifier(base.StatusReceiverMultiService):
    """This is a status notifier which sends email to a list of recipients
    upon the completion of each build. It can be configured to only send out
    mail for certain builds, and only send messages when the build fails, or
    when it transitions from success to failure. It can also be configured to
    include various build logs in each message.

    By default, the message will be sent to the Interested Users list, which
    includes all developers who made changes in the build. You can add
    additional recipients with the extraRecipients argument.

    To get a simple one-message-per-build (say, for a mailing list), use
    sendToInterestedUsers=False, extraRecipients=['listaddr@example.org']

    Each MailNotifier sends mail to a single set of recipients. To send
    different kinds of mail to different recipients, use multiple
    MailNotifiers.
    """

    implements(interfaces.IEmailSender)

    compare_attrs = ["extraRecipients", "lookup", "fromaddr", "mode",
                     "categories", "builders", "addLogs", "relayhost",
                     "subject", "sendToInterestedUsers", "customMesg",
                     "messageFormatter", "extraHeaders"]

    possible_modes = ("change", "failing", "passing", "problem", "warnings")

    def __init__(self, fromaddr, mode=("failing", "passing", "warnings"),
                 categories=None, builders=None, addLogs=False,
                 relayhost="localhost", buildSetSummary=False,
                 subject="buildbot %(result)s in %(title)s on %(builder)s",
                 lookup=None, extraRecipients=[],
                 sendToInterestedUsers=True, customMesg=None,
                 messageFormatter=defaultMessage, extraHeaders=None,
                 addPatch=True, useTls=False, 
                 smtpUser=None, smtpPassword=None, smtpPort=25):
        """
        @type  fromaddr: string
        @param fromaddr: the email address to be used in the 'From' header.
        @type  sendToInterestedUsers: boolean
        @param sendToInterestedUsers: if True (the default), send mail to all
                                      of the Interested Users. If False, only
                                      send mail to the extraRecipients list.

        @type  extraRecipients: tuple of strings
        @param extraRecipients: a list of email addresses to which messages
                                should be sent (in addition to the
                                InterestedUsers list, which includes any
                                developers who made Changes that went into this
                                build). It is a good idea to create a small
                                mailing list and deliver to that, then let
                                subscribers come and go as they please.  The
                                addresses in this list are used literally (they
                                are not processed by lookup).

        @type  subject: string
        @param subject: a string to be used as the subject line of the message.
                        %(builder)s will be replaced with the name of the
                        builder which provoked the message.

        @type  mode: list of strings
        @param mode: a list of MailNotifer.possible_modes:
                     - "change":  send mail about builds which change status
                     - "failing": send mail about builds which fail
                     - "passing": send mail about builds which succeed
                     - "problem": send mail about a build which failed
                                  when the previous build passed
                     - "warnings": send mail if a build contain warnings
                     Defaults to ("failing", "passing", "warnings").

        @type  builders: list of strings
        @param builders: a list of builder names for which mail should be
                         sent. Defaults to None (send mail for all builds).
                         Use either builders or categories, but not both.

        @type  categories: list of strings
        @param categories: a list of category names to serve status
                           information for. Defaults to None (all
                           categories). Use either builders or categories,
                           but not both.

        @type  addLogs: boolean
        @param addLogs: if True, include all build logs as attachments to the
                        messages.  These can be quite large. This can also be
                        set to a list of log names, to send a subset of the
                        logs. Defaults to False.

        @type  addPatch: boolean
        @param addPatch: if True, include the patch when the source stamp
                         includes one.

        @type  relayhost: string
        @param relayhost: the host to which the outbound SMTP connection
                          should be made. Defaults to 'localhost'
                          
        @type  buildSetSummary: boolean
        @param buildSetSummary: if True, this notifier will only send a summary
                                email when a buildset containing any of its
                                watched builds completes
                                
        @type  lookup:    implementor of {IEmailLookup}
        @param lookup:    object which provides IEmailLookup, which is
                          responsible for mapping User names for Interested
                          Users (which come from the VC system) into valid
                          email addresses. If not provided, the notifier will
                          only be able to send mail to the addresses in the
                          extraRecipients list. Most of the time you can use a
                          simple Domain instance. As a shortcut, you can pass
                          as string: this will be treated as if you had provided
                          Domain(str). For example, lookup='twistedmatrix.com'
                          will allow mail to be sent to all developers whose SVN
                          usernames match their twistedmatrix.com account names.

        @type  customMesg: func
        @param customMesg: (this function is deprecated)

        @type  messageFormatter: func
        @param messageFormatter: function taking (mode, name, build, result,
                                 master_status) and returning a dictionary
                                 containing two required keys "body" and "type",
                                 with a third optional key, "subject". The
                                 "body" key gives a string that contains the
                                 complete text of the message. The "type" key
                                 is the message type ('plain' or 'html'). The
                                 'html' type should be used when generating an
                                 HTML message.  The optional "subject" key
                                 gives the subject for the email.

        @type  extraHeaders: dict
        @param extraHeaders: A dict of extra headers to add to the mail. It's
                             best to avoid putting 'To', 'From', 'Date',
                             'Subject', or 'CC' in here. Both the names and
                             values may be WithProperties instances.

        @type useTls: boolean
        @param useTls: Send emails using TLS and authenticate with the 
                       smtp host. Defaults to False.

        @type smtpUser: string
        @param smtpUser: The user that will attempt to authenticate with the
                         relayhost when useTls is True.

        @type smtpPassword: string
        @param smtpPassword: The password that smtpUser will use when
                             authenticating with relayhost.

        @type smtpPort: int
        @param smtpPort: The port that will be used when connecting to the
                         relayhost. Defaults to 25.
        """
        base.StatusReceiverMultiService.__init__(self)

        if not isinstance(extraRecipients, (list, tuple)):
            config.error("extraRecipients must be a list or tuple")
        else:
            for r in extraRecipients:
                if not isinstance(r, str) or not VALID_EMAIL.search(r):
                    config.error(
                            "extra recipient %r is not a valid email" % (r,))
        self.extraRecipients = extraRecipients
        self.sendToInterestedUsers = sendToInterestedUsers
        self.fromaddr = fromaddr
        if isinstance(mode, basestring):
            if mode == "all":
                mode = ("failing", "passing", "warnings")
            elif mode == "warnings":
                mode = ("failing", "warnings")
            else:
                mode = (mode,)
        for m in mode:
            if m not in self.possible_modes:
                config.error(
                    "mode %s is not a valid mode" % (m,))
        self.mode = mode
        self.categories = categories
        self.builders = builders
        self.addLogs = addLogs
        self.relayhost = relayhost
        if '\n' in subject:
            config.error(
                'Newlines are not allowed in email subjects')
        self.subject = subject
        if lookup is not None:
            if type(lookup) is str:
                lookup = Domain(lookup)
            assert interfaces.IEmailLookup.providedBy(lookup)
        self.lookup = lookup
        self.customMesg = customMesg
        self.messageFormatter = messageFormatter
        if extraHeaders:
            if not isinstance(extraHeaders, dict):
                config.error("extraHeaders must be a dictionary")
        self.extraHeaders = extraHeaders
        self.addPatch = addPatch
        self.useTls = useTls
        self.smtpUser = smtpUser
        self.smtpPassword = smtpPassword
        self.smtpPort = smtpPort
        self.buildSetSummary = buildSetSummary
        self.buildSetSubscription = None
        self.watched = []
        self.master_status = None

        # you should either limit on builders or categories, not both
        if self.builders != None and self.categories != None:
            config.error(
                "Please specify only builders or categories to include - " +
                "not both.")

        if customMesg:
            config.error(
                "customMesg is deprecated; use messageFormatter instead")

    def setServiceParent(self, parent):
        """
        @type  parent: L{buildbot.master.BuildMaster}
        """
        base.StatusReceiverMultiService.setServiceParent(self, parent)
        self.master_status = self.parent
        self.master_status.subscribe(self)
        self.master = self.master_status.master

    def startService(self):
        if self.buildSetSummary:
            self.buildSetSubscription = \
            self.master.subscribeToBuildsetCompletions(self.buildsetFinished)
 
        base.StatusReceiverMultiService.startService(self)

    def stopService(self):
        if self.buildSetSubscription is not None:
            self.buildSetSubscription.unsubscribe()
            self.buildSetSubscription = None
            
        return base.StatusReceiverMultiService.stopService(self)

    def disownServiceParent(self):
        self.master_status.unsubscribe(self)
        self.master_status = None
        for w in self.watched:
            w.unsubscribe(self)
        return base.StatusReceiverMultiService.disownServiceParent(self)

    def builderAdded(self, name, builder):
        # only subscribe to builders we are interested in
        if self.categories != None and builder.category not in self.categories:
            return None

        self.watched.append(builder)
        return self # subscribe to this builder

    def builderRemoved(self, name):
        pass

    def builderChangedState(self, name, state):
        pass

    def buildStarted(self, name, build):
        pass

    def isMailNeeded(self, build, results):
        # here is where we actually do something.
        builder = build.getBuilder()
        if self.builders is not None and builder.name not in self.builders:
            return False # ignore this build
        if self.categories is not None and \
               builder.category not in self.categories:
            return False # ignore this build

        prev = build.getPreviousBuild()
        if "change" in self.mode:
            if prev and prev.getResults() != results:
                return True
        if "failing" in self.mode and results == FAILURE:
            return True
        if "passing" in self.mode and results == SUCCESS:
            return True
        if "problem" in self.mode and results == FAILURE:
            if prev and prev.getResults() != FAILURE:
                return True
        if "warnings" in self.mode and results == WARNINGS:
            return True

        return False

    def buildFinished(self, name, build, results):
        if ( not self.buildSetSummary and
             self.isMailNeeded(build, results) ):
            # for testing purposes, buildMessage returns a Deferred that fires
            # when the mail has been sent. To help unit tests, we return that
            # Deferred here even though the normal IStatusReceiver.buildFinished
            # signature doesn't do anything with it. If that changes (if
            # .buildFinished's return value becomes significant), we need to
            # rearrange this.
            return self.buildMessage(name, [build], results)
        return None
    
    def _gotBuilds(self, res, buildset):
        builds = []
        for (builddictlist, builder) in res:
            for builddict in builddictlist:
                build = builder.getBuild(builddict['number'])
                if build is not None and self.isMailNeeded(build, build.results):
                    builds.append(build)

        if builds:
            self.buildMessage("Buildset Complete: " + buildset['reason'], builds,
                              buildset['results'])
        
    def _gotBuildRequests(self, breqs, buildset):
        dl = []
        for breq in breqs:
            buildername = breq['buildername']
            builder = self.master_status.getBuilder(buildername)
            d = self.master.db.builds.getBuildsForRequest(breq['brid'])
            d.addCallback(lambda builddictlist: (builddictlist, builder))
            dl.append(d)
        d = defer.gatherResults(dl)
        d.addCallback(self._gotBuilds, buildset)

    def _gotBuildSet(self, buildset, bsid):
        d = self.master.db.buildrequests.getBuildRequests(bsid=bsid)
        d.addCallback(self._gotBuildRequests, buildset)
        
    def buildsetFinished(self, bsid, result):
        d = self.master.db.buildsets.getBuildset(bsid=bsid)
        d.addCallback(self._gotBuildSet, bsid)
            
        return d

    def getCustomMesgData(self, mode, name, build, results, master_status):
        #
        # logs is a list of tuples that contain the log
        # name, log url, and the log contents as a list of strings.
        #
        logs = list()
        for logf in build.getLogs():
            logStep = logf.getStep()
            stepName = logStep.getName()
            logStatus, dummy = logStep.getResults()
            logName = logf.getName()
            logs.append(('%s.%s' % (stepName, logName),
                         '%s/steps/%s/logs/%s' % (
                             master_status.getURLForThing(build),
                             stepName, logName),
                         logf.getText().splitlines(),
                         logStatus))

        attrs = {'builderName': name,
                 'title': master_status.getTitle(),
                 'mode': mode,
                 'result': Results[results],
                 'buildURL': master_status.getURLForThing(build),
                 'buildbotURL': master_status.getBuildbotURL(),
                 'buildText': build.getText(),
                 'buildProperties': build.getProperties(),
                 'slavename': build.getSlavename(),
                 'reason':  build.getReason().replace('\n', ''),
                 'responsibleUsers': build.getResponsibleUsers(),
                 'branch': "",
                 'revision': "",
                 'patch': "",
                 'patch_info': "",
                 'changes': [],
                 'logs': logs}

        ss = None
        ss_list = build.getSourceStamps()

        if ss_list:
            if len(ss_list) == 1:
                ss = ss_list[0]
                if ss:
                    attrs['branch'] = ss.branch
                    attrs['revision'] = ss.revision
                    attrs['patch'] = ss.patch
                    attrs['patch_info'] = ss.patch_info
                    attrs['changes'] = ss.changes[:]
            else:
                for key in ['branch', 'revision', 'patch', 'patch_info', 'changes']:
                    attrs[key] = {}
                for ss in ss_list:
                    attrs['branch'][ss.codebase] = ss.branch
                    attrs['revision'][ss.codebase] = ss.revision
                    attrs['patch'][ss.codebase] = ss.patch
                    attrs['patch_info'][ss.codebase] = ss.patch_info
                    attrs['changes'][ss.codebase] = ss.changes[:]

        return attrs

    def patch_to_attachment(self, patch, index):
        # patches don't come with an encoding.  If the patch is valid utf-8,
        # we'll attach it as MIMEText; otherwise, it gets attached as a binary
        # file.  This will suit the vast majority of cases, since utf8 is by
        # far the most common encoding.
        if type(patch[1]) != types.UnicodeType:
            try:
                    unicode = patch[1].decode('utf8')
            except UnicodeDecodeError:
                unicode = None
        else:
            unicode = patch[1]

        if unicode:
            a = MIMEText(unicode.encode(ENCODING), _charset=ENCODING)
        else:
            # MIMEApplication is not present in Python-2.4 :(
            a = MIMENonMultipart('application', 'octet-stream')
            a.set_payload(patch[1])
        a.add_header('Content-Disposition', "attachment",
                    filename="source patch " + str(index) )
        return a

    def createEmail(self, msgdict, builderName, title, results, builds=None,
                    patches=None, logs=None):
        text = msgdict['body'].encode(ENCODING)
        type = msgdict['type']
        if 'subject' in msgdict:
            subject = msgdict['subject'].encode(ENCODING)
        else:
            subject = self.subject % { 'result': Results[results],
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
            m.attach(MIMEText(text, type, ENCODING))
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
                name = "%s.%s" % (log.getStep().getName(),
                                  log.getName())
                if ( self._shouldAttachLog(log.getName()) or
                     self._shouldAttachLog(name) ):
                    text = log.getText()
                    if not isinstance(text, unicode):
                        text = text.decode(LOG_ENCODING)
                    a = MIMEText(text.encode(ENCODING),
                                 _charset=ENCODING)
                    a.add_header('Content-Disposition', "attachment",
                                 filename=name)
                    m.attach(a)

        #@todo: is there a better way to do this?
        # Add any extra headers that were requested, doing WithProperties
        # interpolation if only one build was given
        if self.extraHeaders:
            if len(builds) == 1:
                d = builds[0].render(self.extraHeaders)
            else:
                d = defer.succeed(self.extraHeaders)
            @d.addCallback
            def addExtraHeaders(extraHeaders):
                for k,v in extraHeaders.items():
                    if k in m:
                        twlog.msg("Warning: Got header " + k +
                          " in self.extraHeaders "
                          "but it already exists in the Message - "
                          "not adding it.")
                    m[k] = v
            d.addCallback(lambda _: m)
            return d
    
        return defer.succeed(m)
    
    def buildMessageDict(self, name, build, results):
        if self.customMesg:
            # the customMesg stuff can be *huge*, so we prefer not to load it
            attrs = self.getCustomMesgData(self.mode, name, build, results,
                                           self.master_status)
            text, type = self.customMesg(attrs)
            msgdict = { 'body' : text, 'type' : type }
        else:
            msgdict = self.messageFormatter(self.mode, name, build, results,
                                            self.master_status)
        
        return msgdict


    def buildMessage(self, name, builds, results):
        patches = []
        logs = []
        msgdict = {"body":""}
        
        for build in builds:
            ss_list = build.getSourceStamps()
            if self.addPatch:
                for ss in ss_list:
                    if ss.patch:
                        patches.append(ss.patch)
            if self.addLogs:
                logs.extend(build.getLogs())
            
            tmp = self.buildMessageDict(name=build.getBuilder().name,
                                        build=build, results=build.results)
            msgdict['body'] += tmp['body']
            msgdict['body'] += '\n\n'
            msgdict['type'] = tmp['type']
            if "subject" in tmp:
                msgdict['subject'] = tmp['subject']

        d = self.createEmail(msgdict, name, self.master_status.getTitle(),
                             results, builds, patches, logs)

        @d.addCallback
        def getRecipients(m):
            # now, who is this message going to?
            if self.sendToInterestedUsers:
                dl = []
                for build in builds:
                    if self.lookup:
                        d = self.useLookup(build)
                    else:
                        d = self.useUsers(build)
                    dl.append(d)
                d = defer.gatherResults(dl)
            else:
                d = defer.succeed([])
            d.addCallback(self._gotRecipients, m)
        return d

    def useLookup(self, build):
        dl = []
        for u in build.getInterestedUsers():
            d = defer.maybeDeferred(self.lookup.getAddress, u)
            dl.append(d)
        return defer.gatherResults(dl)

    def useUsers(self, build):
        dl = []
        ss = None
        ss_list = build.getSourceStamps()
        for ss in ss_list:
            for change in ss.changes:
                d = self.master.db.changes.getChangeUids(change.number)
                def getContacts(uids):
                    def uidContactPair(contact, uid):
                        return (contact, uid)
                    contacts = []
                    for uid in uids:
                        d = users.getUserContact(self.master,
                                contact_type='email',
                                uid=uid)
                        d.addCallback(lambda contact: uidContactPair(contact, uid))
                        contacts.append(d)
                    return defer.gatherResults(contacts)
                d.addCallback(getContacts)
                def logNoMatch(contacts):
                    for pair in contacts:
                        contact, uid = pair
                        if contact is None:
                            twlog.msg("Unable to find email for uid: %r" % uid)
                    return [pair[0] for pair in contacts]
                d.addCallback(logNoMatch)
                def addOwners(recipients):
                    owners = [e for e in build.getInterestedUsers()
                              if e not in build.getResponsibleUsers()]
                    recipients.extend(owners)
                    return recipients
                d.addCallback(addOwners)
                dl.append(d)
        d = defer.gatherResults(dl)
        @d.addCallback
        def gatherRecipients(res):
            recipients = []
            map(recipients.extend, res)
            return recipients
        return d

    def _shouldAttachLog(self, logname):
        if type(self.addLogs) is bool:
            return self.addLogs
        return logname in self.addLogs

    def _gotRecipients(self, rlist, m):
        to_recipients = set()
        cc_recipients = set()

        for r in reduce(list.__add__, rlist, []):
            if r is None: # getAddress didn't like this address
                continue

            # Git can give emails like 'User' <user@foo.com>@foo.com so check
            # for two @ and chop the last
            if r.count('@') > 1:
                r = r[:r.rindex('@')]

            if VALID_EMAIL.search(r):
                to_recipients.add(r)
            else:
                twlog.msg("INVALID EMAIL: %r" + r)

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

        return self.sendMessage(m, list(to_recipients | cc_recipients))

    def sendmail(self, s, recipients):
        result = defer.Deferred()
        
        if have_ssl and self.useTls:
            client_factory = ssl.ClientContextFactory()
            client_factory.method = SSLv3_METHOD
        else:
            client_factory = None

        if self.smtpUser and self.smtpPassword:
            useAuth = True
        else:
            useAuth = False
        
        if not ESMTPSenderFactory:
            raise RuntimeError("twisted-mail is not installed - cannot "
                               "send mail")
        sender_factory = ESMTPSenderFactory(
            self.smtpUser, self.smtpPassword,
            self.fromaddr, recipients, StringIO(s),
            result, contextFactory=client_factory,
            requireTransportSecurity=self.useTls,
            requireAuthentication=useAuth)

        reactor.connectTCP(self.relayhost, self.smtpPort, sender_factory)
        
        return result

    def sendMessage(self, m, recipients):
        s = m.as_string()
        twlog.msg("sending mail (%d bytes) to" % len(s), recipients)
        return self.sendmail(s, recipients)

