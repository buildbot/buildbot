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

from email.Message import Message
from email.Utils import formatdate
from email.MIMEText import MIMEText
from email.MIMEMultipart import MIMEMultipart
from StringIO import StringIO
import urllib

from zope.interface import implements
from twisted.internet import defer, reactor
from twisted.mail.smtp import ESMTPSenderFactory
from twisted.python import log as twlog

have_ssl = True
try:
    from twisted.internet import ssl
    from OpenSSL.SSL import SSLv3_METHOD
except ImportError:
    have_ssl = False

from buildbot import interfaces, util
from buildbot.status import base
from buildbot.status.results import FAILURE, SUCCESS, Results

VALID_EMAIL = re.compile("[a-zA-Z0-9\.\_\%\-\+]+@[a-zA-Z0-9\.\_\%\-]+.[a-zA-Z]{2,6}")

ENCODING = 'utf8'

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
    result = Results[results]
    ss = build.getSourceStamp()

    text = ""
    if mode == "all":
        text += "The Buildbot has finished a build"
    elif mode == "failing":
        text += "The Buildbot has detected a failed build"
    elif mode == "warnings":
        text += "The Buildbot has detected a problem in the build"
    elif mode == "passing":
        text += "The Buildbot has detected a passing build"
    elif mode == "change" and result == 'success':
        text += "The Buildbot has detected a restored build"
    else:    
        text += "The Buildbot has detected a new failure"
    if ss and ss.project:
        project = ss.project
    else:
        project = master_status.getTitle()
    text += " on builder %s while building %s.\n" % (name, project)
    if master_status.getURLForThing(build):
        text += "Full details are available at:\n %s\n" % master_status.getURLForThing(build)
    text += "\n"

    if master_status.getBuildbotURL():
        text += "Buildbot URL: %s\n\n" % urllib.quote(master_status.getBuildbotURL(), '/:')

    text += "Buildslave for this Build: %s\n\n" % build.getSlavename()
    text += "Build Reason: %s\n" % build.getReason()

    source = ""
    if ss and ss.branch:
        source += "[branch %s] " % ss.branch
    if ss and ss.revision:
        source += str(ss.revision)
    else:
        source += "HEAD"
    if ss and ss.patch:
        source += " (plus patch)"

    text += "Build Source Stamp: %s\n" % source

    text += "Blamelist: %s\n" % ",".join(build.getResponsibleUsers())

    text += "\n"

    t = build.getText()
    if t:
        t = ": " + " ".join(t)
    else:
        t = ""

    if result == 'success':
        text += "Build succeeded!\n"
    elif result == 'warnings':
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

    possible_modes = ('all', 'failing', 'problem', 'change', 'passing', 'warnings')

    def __init__(self, fromaddr, mode="all", categories=None, builders=None,
                 addLogs=False, relayhost="localhost", buildSetSummary=False,
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

        @type  extraRecipients: tuple of string
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

        @type  mode: string (defaults to all)
        @param mode: one of MailNotifer.possible_modes:
                     - 'all': send mail about all builds, passing and failing
                     - 'failing': only send mail about builds which fail
                     - 'warnings': send mail if builds contain warnings or fail 
                     - 'passing': only send mail about builds which succeed
                     - 'problem': only send mail about a build which failed
                     when the previous build passed
                     - 'change': only send mail about builds who change status

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
        assert isinstance(extraRecipients, (list, tuple))
        for r in extraRecipients:
            assert isinstance(r, str)
            # require full email addresses, not User names
            assert VALID_EMAIL.search(r), "%s is not a valid email" % r 
        self.extraRecipients = extraRecipients
        self.sendToInterestedUsers = sendToInterestedUsers
        self.fromaddr = fromaddr
        assert mode in MailNotifier.possible_modes
        self.mode = mode
        self.categories = categories
        self.builders = builders
        self.addLogs = addLogs
        self.relayhost = relayhost
        self.subject = subject
        if lookup is not None:
            if type(lookup) is str:
                lookup = Domain(lookup)
            assert interfaces.IEmailLookup.providedBy(lookup)
        self.lookup = lookup
        self.customMesg = customMesg
        self.messageFormatter = messageFormatter
        if extraHeaders:
            assert isinstance(extraHeaders, dict)
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
            twlog.err("Please specify only builders or categories to include not both.")
            raise interfaces.ParameterError("Please specify only builders or categories to include not both.")

        if customMesg:
            twlog.msg("customMesg is deprecated; please use messageFormatter instead")

    def setServiceParent(self, parent):
        """
        @type  parent: L{buildbot.master.BuildMaster}
        """
        base.StatusReceiverMultiService.setServiceParent(self, parent)
        self.setup()

    def setup(self):
        self.master_status = self.parent.getStatus()
        self.master_status.subscribe(self)
        
            
    def startService(self):
        if self.buildSetSummary:
            self.buildSetSubscription = \
            self.parent.subscribeToBuildsetCompletions(self.buildsetFinished)
 
        base.StatusReceiverMultiService.startService(self)
        
   
    def stopService(self):
        if self.buildSetSubscription is not None:
            self.buildSetSubscription.unsubscribe()
            self.buildSetSubscription = None
            
        return base.StatusReceiverMultiService.stopService(self)

    def disownServiceParent(self):
        self.master_status.unsubscribe(self)
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

        if self.mode == "warnings" and results == SUCCESS:
            return False
        if self.mode == "failing" and results != FAILURE:
            return False
        if self.mode == "passing" and results != SUCCESS:
            return False
        if self.mode == "problem":
            if results != FAILURE:
                return False
            prev = build.getPreviousBuild()
            if prev and prev.getResults() == FAILURE:
                return False
        if self.mode == "change":
            prev = build.getPreviousBuild()
            if not prev or prev.getResults() == results:
                return False
        
        return True

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
    
    def _gotBuilds(self, res, builddicts, buildset, builders):
        builds = []
        for (builddictlist, builder) in zip(builddicts, builders):
                for builddict in builddictlist:
                    build = builder.getBuild(builddict['number'])
                    if self.isMailNeeded(build, build.results):
                        builds.append(build)

        self.buildMessage("Buildset Complete: " + buildset['reason'], builds,
                          buildset['results'])
        
    def _gotBuildRequests(self, breqs, buildset):
        builddicts = []
        builders =[]
        dl = []
        for breq in breqs:
            buildername = breq['buildername']
            builders.append(self.master_status.getBuilder(buildername))
            d = self.parent.db.builds.getBuildsForRequest(breq['brid'])
            d.addCallback(builddicts.append)
            dl.append(d)
        d = defer.DeferredList(dl)
        d.addCallback(self._gotBuilds, builddicts, buildset, builders)

    def _gotBuildSet(self, buildset, bsid):
        d = self.parent.db.buildrequests.getBuildRequests(bsid=bsid)
        d.addCallback(self._gotBuildRequests, buildset)
        
    def buildsetFinished(self, bsid, result):
        d = self.parent.db.buildsets.getBuildset(bsid=bsid)
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
                 'reason':  build.getReason(),
                 'responsibleUsers': build.getResponsibleUsers(),
                 'branch': "",
                 'revision': "",
                 'patch': "",
                 'changes': [],
                 'logs': logs}

        ss = build.getSourceStamp()
        if ss:
            attrs['branch'] = ss.branch
            attrs['revision'] = ss.revision
            attrs['patch'] = ss.patch
            attrs['changes'] = ss.changes[:]

        return attrs

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
                a = MIMEText(patch[1].encode(ENCODING), _charset=ENCODING)
                a.add_header('Content-Disposition', "attachment",
                         filename="source patch " + str(i) )
                m.attach(a)
        if logs:
            for log in logs:
                name = "%s.%s" % (log.getStep().getName(),
                                  log.getName())
                if ( self._shouldAttachLog(log.getName()) or
                     self._shouldAttachLog(name) ):
                    a = MIMEText(log.getText().encode(ENCODING), 
                                 _charset=ENCODING)
                    a.add_header('Content-Disposition', "attachment",
                                 filename=name)
                    m.attach(a)

        #@todo: is there a better way to do this?
        # Add any extra headers that were requested, doing WithProperties
        # interpolation if only one build was given
        if self.extraHeaders:
            for k,v in self.extraHeaders.items():
                if len(builds == 1):
                    k = builds[0].render(k)
                if k in m:
                    twlog.msg("Warning: Got header " + k +
                      " in self.extraHeaders "
                      "but it already exists in the Message - "
                      "not adding it.")
                continue
                if len(builds == 1):
                    m[k] = builds[0].render(v)
                else:
                    m[k] = v
    
        return m
    
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
            ss = build.getSourceStamp()
            if ss and ss.patch and self.addPatch:
                patches.append(ss.patch)
            if self.addLogs:
                logs.append(build.getLogs())
            twlog.err("LOG: %s" % str(logs))
            
            tmp = self.buildMessageDict(name=build.getBuilder().name,
                                        build=build, results=build.results)
            msgdict['body'] += tmp['body']
            msgdict['body'] += '\n\n'
            msgdict['type'] = tmp['type']
            
        m = self.createEmail(msgdict, name, self.master_status.getTitle(),
                             results, builds, patches, logs)

        # now, who is this message going to?
        dl = []
        recipients = []
        if self.sendToInterestedUsers and self.lookup:
            for build in builds:
                for u in build.getInterestedUsers():
                    d = defer.maybeDeferred(self.lookup.getAddress, u)
                    d.addCallback(recipients.append)
                    dl.append(d)
        d = defer.DeferredList(dl)
        d.addCallback(self._gotRecipients, recipients, m)
        return d

    def _shouldAttachLog(self, logname):
        if type(self.addLogs) is bool:
            return self.addLogs
        return logname in self.addLogs

    def _gotRecipients(self, res, rlist, m):
        to_recipients = set()
        cc_recipients = set()

        for r in rlist:
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

