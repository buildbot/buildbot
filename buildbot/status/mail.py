# -*- test-case-name: buildbot.test.test_status -*-

# the email.MIMEMultipart module is only available in python-2.2.2 and later
import re

from email.Message import Message
from email.Utils import formatdate
from email.MIMEText import MIMEText
try:
    from email.MIMEMultipart import MIMEMultipart
    canDoAttachments = True
except ImportError:
    canDoAttachments = False
import urllib

from zope.interface import implements
from twisted.internet import defer
from twisted.mail.smtp import sendmail
from twisted.python import log as twlog

from buildbot import interfaces, util
from buildbot.status import base
from buildbot.status.builder import FAILURE, SUCCESS, WARNINGS, Results

import sys
if sys.version_info[:3] < (2,4,0):
    from sets import Set as set

VALID_EMAIL = re.compile("[a-zA-Z0-9\.\_\%\-\+]+@[a-zA-Z0-9\.\_\%\-]+.[a-zA-Z]{2,6}")

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

    def __init__(self, fromaddr, mode="all", categories=None, builders=None,
                 addLogs=False, relayhost="localhost",
                 subject="buildbot %(result)s in %(projectName)s on %(builder)s",
                 lookup=None, extraRecipients=[],
                 sendToInterestedUsers=True, customMesg=None,
                 messageFormatter=None, extraHeaders=None, addPatch=True):
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
                                subscribers come and go as they please.

        @type  subject: string
        @param subject: a string to be used as the subject line of the message.
                        %(builder)s will be replaced with the name of the
                        builder which provoked the message.

        @type  mode: string (defaults to all)
        @param mode: one of:
                     - 'all': send mail about all builds, passing and failing
                     - 'failing': only send mail about builds which fail
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

        @type  lookup:    implementor of {IEmailLookup}
        @param lookup:    object which provides IEmailLookup, which is
                          responsible for mapping User names (which come from
                          the VC system) into valid email addresses. If not
                          provided, the notifier will only be able to send mail
                          to the addresses in the extraRecipients list. Most of
                          the time you can use a simple Domain instance. As a
                          shortcut, you can pass as string: this will be
                          treated as if you had provided Domain(str). For
                          example, lookup='twistedmatrix.com' will allow mail
                          to be sent to all developers whose SVN usernames
                          match their twistedmatrix.com account names.
                          
        @type  customMesg: func
        @param customMesg: (this function is deprecated)

        @type  messageFormatter: func
        @param messageFormatter: function taking (mode, name, build, result,
                                 master_status ) and returning a dictionary
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
        """

        base.StatusReceiverMultiService.__init__(self)
        assert isinstance(extraRecipients, (list, tuple))
        for r in extraRecipients:
            assert isinstance(r, str)
            assert VALID_EMAIL.search(r) # require full email addresses, not User names
        self.extraRecipients = extraRecipients
        self.sendToInterestedUsers = sendToInterestedUsers
        self.fromaddr = fromaddr
        assert mode in ('all', 'failing', 'problem', 'change', 'passing')
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
        self.watched = []
        self.master_status = None

        # you should either limit on builders or categories, not both
        if self.builders != None and self.categories != None:
            twlog.err("Please specify only builders to ignore or categories to include")
            raise # FIXME: the asserts above do not raise some Exception either

        if customMesg and messageFormatter:
            twlog.err("Specify only one of customMesg and messageFormatter")
            self.customMesg = None

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
    def buildFinished(self, name, build, results):
        # here is where we actually do something.
        builder = build.getBuilder()
        if self.builders is not None and name not in self.builders:
            return # ignore this build
        if self.categories is not None and \
               builder.category not in self.categories:
            return # ignore this build

        if self.mode == "failing" and results != FAILURE:
            return
        if self.mode == "passing" and results != SUCCESS:
            return
        if self.mode == "problem":
            if results != FAILURE:
                return
            prev = build.getPreviousBuild()
            if prev and prev.getResults() == FAILURE:
                return
        if self.mode == "change":
            prev = build.getPreviousBuild()
            if not prev or prev.getResults() == results:
                if prev:
                    print prev.getResults()
                else:
                    print "no prev"
                return
        # for testing purposes, buildMessage returns a Deferred that fires
        # when the mail has been sent. To help unit tests, we return that
        # Deferred here even though the normal IStatusReceiver.buildFinished
        # signature doesn't do anything with it. If that changes (if
        # .buildFinished's return value becomes significant), we need to
        # rearrange this.
        return self.buildMessage(name, build, results)

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
                         '%s/steps/%s/logs/%s' % (master_status.getURLForThing(build), stepName, logName),
                         logf.getText().splitlines(),
                         logStatus))

        properties = build.getProperties()
                
        attrs = {'builderName': name,
                 'projectName': master_status.getProjectName(),
                 'mode': mode,
                 'result': Results[results],
                 'buildURL': master_status.getURLForThing(build),
                 'buildbotURL': master_status.getBuildbotURL(),
                 'buildText': build.getText(),
                 'buildProperties': properties,
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

    def defaultMessage(self, mode, name, build, results, master_status):
        """Generate a buildbot mail message and return a tuple of message text
        and type."""
        result = Results[results]

        text = ""
        if mode == "all":
            text += "The Buildbot has finished a build"
        elif mode == "failing":
            text += "The Buildbot has detected a failed build"
        elif mode == "passing":
            text += "The Buildbot has detected a passing build"
        elif mode == "change" and result == 'success':
            text += "The Buildbot has detected a restored build"
        else:    
            text += "The Buildbot has detected a new failure"
        text += " of %s on %s.\n" % (name, master_status.getProjectName())
        if master_status.getURLForThing(build):
            text += "Full details are available at:\n %s\n" % master_status.getURLForThing(build)
        text += "\n"

        if master_status.getBuildbotURL():
            text += "Buildbot URL: %s\n\n" % urllib.quote(master_status.getBuildbotURL(), '/:')

        text += "Buildslave for this Build: %s\n\n" % build.getSlavename()
        text += "Build Reason: %s\n" % build.getReason()

        source = ""
        ss = build.getSourceStamp()
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

    def buildMessage(self, name, build, results):
        if self.customMesg:
            # the customMesg stuff can be *huge*, so we prefer not to load it
            attrs = self.getCustomMesgData(self.mode, name, build, results, self.master_status)
            text, type = self.customMesg(attrs)
            msgdict = { 'body' : text, 'type' : type }
        elif self.messageFormatter:
            msgdict = self.messageFormatter(self.mode, name, build, results, self.master_status)
        else:
            msgdict = self.defaultMessage(self.mode, name, build, results, self.master_status)

        text = msgdict['body']
        type = msgdict['type']
        if 'subject' in msgdict:
            subject = msgdict['subject']
        else:
            subject = self.subject % { 'result': Results[results],
                                       'projectName': self.master_status.getProjectName(),
                                       'builder': name,
                                       }


        assert type in ('plain', 'html'), "'%s' message type must be 'plain' or 'html'." % type

        haveAttachments = False
        ss = build.getSourceStamp()
        if (ss and ss.patch and self.addPatch) or self.addLogs:
            haveAttachments = True
            if not canDoAttachments:
                twlog.msg("warning: I want to send mail with attachments, "
                          "but this python is too old to have "
                          "email.MIMEMultipart . Please upgrade to python-2.3 "
                          "or newer to enable addLogs=True")

        if haveAttachments and canDoAttachments:
            m = MIMEMultipart()
            m.attach(MIMEText(text, type))
        else:
            m = Message()
            m.set_payload(text)
            m.set_type("text/%s" % type)

        m['Date'] = formatdate(localtime=True)
        m['Subject'] = subject
        m['From'] = self.fromaddr
        # m['To'] is added later

        if ss and ss.patch and self.addPatch:
            patch = ss.patch
            a = MIMEText(patch[1])
            a.add_header('Content-Disposition', "attachment",
                         filename="source patch")
            m.attach(a)
        if self.addLogs:
            for log in build.getLogs():
                name = "%s.%s" % (log.getStep().getName(),
                                  log.getName())
                if self._shouldAttachLog(log.getName()) or self._shouldAttachLog(name):
                    a = MIMEText(log.getText())
                    a.add_header('Content-Disposition', "attachment",
                                 filename=name)
                    m.attach(a)

        # Add any extra headers that were requested, doing WithProperties
        # interpolation if necessary
        if self.extraHeaders:
            for k,v in self.extraHeaders.items():
                k = properties.render(k)
                if k in m:
                    twlog("Warning: Got header " + k + " in self.extraHeaders "
                          "but it already exists in the Message - "
                          "not adding it.")
                    continue
                m[k] = properties.render(v)

        # now, who is this message going to?
        dl = []
        recipients = []
        if self.sendToInterestedUsers and self.lookup:
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
        recipients = set()

        for r in rlist:
            if r is None: # getAddress didn't like this address
                continue

            # Git can give emails like 'User' <user@foo.com>@foo.com so check
            # for two @ and chop the last
            if r.count('@') > 1:
                r = r[:r.rindex('@')]

            if VALID_EMAIL.search(r):
                recipients.add(r)
            else:
                twlog.msg("INVALID EMAIL: %r" + r)

        # if we're sending to interested users move the extra's to the CC
        # list so they can tell if they are also interested in the change
        # unless there are no interested users
        if self.sendToInterestedUsers and len(recipients):
            extra_recips = self.extraRecipients[:]
            extra_recips.sort()
            m['CC'] = ", ".join(extra_recips)
        else:
            [recipients.add(r) for r in self.extraRecipients[:]]

        rlist = list(recipients)
        rlist.sort()
        m['To'] = ", ".join(rlist)

        # The extras weren't part of the TO list so add them now
        if self.sendToInterestedUsers:
            for r in self.extraRecipients:
                recipients.add(r)

        return self.sendMessage(m, list(recipients))

    def sendMessage(self, m, recipients):
        s = m.as_string()
        twlog.msg("sending mail (%d bytes) to" % len(s), recipients)
        return sendmail(self.relayhost, self.fromaddr, recipients, s)
