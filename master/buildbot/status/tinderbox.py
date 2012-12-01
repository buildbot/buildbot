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


from email.Message import Message
from email.Utils import formatdate

from zope.interface import implements
from twisted.internet import defer

from buildbot import interfaces
from buildbot.status import mail
from buildbot.status.results import SUCCESS, WARNINGS, EXCEPTION, RETRY
from buildbot.steps.shell import WithProperties

import gzip, bz2, base64, re, cStringIO

# TODO: docs, maybe a test of some sort just to make sure it actually imports
# and can format email without raising an exception.

class TinderboxMailNotifier(mail.MailNotifier):
    """This is a Tinderbox status notifier. It can send e-mail to a number of
    different tinderboxes or people. E-mails are sent at the beginning and
    upon completion of each build. It can be configured to send out e-mails
    for only certain builds.

    The most basic usage is as follows::
        TinderboxMailNotifier(fromaddr="buildbot@localhost",
                              tree="MyTinderboxTree",
                              extraRecipients=["tinderboxdaemon@host.org"])

    The builder name (as specified in master.cfg) is used as the "build"
    tinderbox option.

    """
    implements(interfaces.IEmailSender)

    compare_attrs = ["extraRecipients", "fromaddr", "categories", "builders",
                     "addLogs", "relayhost", "subject", "binaryURL", "tree",
                     "logCompression", "errorparser", "columnName",
                     "useChangeTime"]

    def __init__(self, fromaddr, tree, extraRecipients,
                 categories=None, builders=None, relayhost="localhost",
                 subject="buildbot %(result)s in %(builder)s", binaryURL="",
                 logCompression="", errorparser="unix", columnName=None,
                 useChangeTime=False):
        """
        @type  fromaddr: string
        @param fromaddr: the email address to be used in the 'From' header.

        @type  tree: string
        @param tree: The Tinderbox tree to post to.
                     When tree is a WithProperties instance it will be
                     interpolated as such. See WithProperties for more detail

        @type  extraRecipients: tuple of string
        @param extraRecipients: E-mail addresses of recipients. This should at
                                least include the tinderbox daemon.

        @type  categories: list of strings
        @param categories: a list of category names to serve status
                           information for. Defaults to None (all
                           categories). Use either builders or categories,
                           but not both.

        @type  builders: list of strings
        @param builders: a list of builder names for which mail should be
                         sent. Defaults to None (send mail for all builds).
                         Use either builders or categories, but not both.

        @type  relayhost: string
        @param relayhost: the host to which the outbound SMTP connection
                          should be made. Defaults to 'localhost'

        @type  subject: string
        @param subject: a string to be used as the subject line of the message.
                        %(builder)s will be replaced with the name of the
                        %builder which provoked the message.
                        This parameter is not significant for the tinderbox
                        daemon.

        @type  binaryURL: string
        @param binaryURL: If specified, this should be the location where final
                          binary for a build is located.
                          (ie. http://www.myproject.org/nightly/08-08-2006.tgz)
                          It will be posted to the Tinderbox.

        @type  logCompression: string
        @param logCompression: The type of compression to use on the log.
                               Valid options are"bzip2" and "gzip". gzip is
                               only known to work on Python 2.4 and above.

        @type  errorparser: string
        @param errorparser: The error parser that the Tinderbox server
                            should use when scanning the log file.
                            Default is "unix".

        @type  columnName: string
        @param columnName: When columnName is None, use the buildername as
                           the Tinderbox column name. When columnName is a
                           string this exact string will be used for all
                           builders that this TinderboxMailNotifier cares
                           about (not recommended). When columnName is a
                           WithProperties instance it will be interpolated
                           as such. See WithProperties for more detail.
        @type  useChangeTime: bool
        @param useChangeTime: When True, the time of the first Change for a
                              build is used as the builddate. When False,
                              the current time is used as the builddate.
        """

        mail.MailNotifier.__init__(self, fromaddr, categories=categories,
                                   builders=builders, relayhost=relayhost,
                                   subject=subject,
                                   extraRecipients=extraRecipients,
                                   sendToInterestedUsers=False)
        assert isinstance(tree, basestring) \
            or isinstance(tree, WithProperties), \
            "tree must be a string or a WithProperties instance"
        self.tree = tree
        self.binaryURL = binaryURL
        self.logCompression = logCompression
        self.errorparser = errorparser
        self.useChangeTime = useChangeTime
        assert columnName is None or type(columnName) is str \
            or isinstance(columnName, WithProperties), \
            "columnName must be None, a string, or a WithProperties instance"
        self.columnName = columnName

    def buildStarted(self, name, build):
        builder = build.getBuilder()
        if self.builders is not None and name not in self.builders:
            return # ignore this Build
        if self.categories is not None and \
                builder.category not in self.categories:
            return # ignore this build
        self.buildMessage(name, build, "building")

    def buildMessage(self, name, build, results):
        text = ""
        res = ""
        # shortform
        t = "tinderbox:"

        if type(self.tree) is str:
            # use the exact string given
            text += "%s tree: %s\n" % (t, self.tree)
        elif isinstance(self.tree, WithProperties):
            # interpolate the WithProperties instance, use that
            text += "%s tree: %s\n" % (t, build.render(self.tree))
        else:
            raise Exception("tree is an unhandled value")

        # the start time
        # getTimes() returns a fractioned time that tinderbox doesn't understand
        builddate = int(build.getTimes()[0])
        # attempt to pull a Change time from this Build's Changes.
        # if that doesn't work, fall back on the current time
        if self.useChangeTime:
            try:
                builddate = build.getChanges()[-1].when
            except:
                pass
        text += "%s builddate: %s\n" % (t, builddate)
        text += "%s status: " % t

        if results == "building":
            res = "building"
            text += res
        elif results == SUCCESS:
            res = "success"
            text += res
        elif results == WARNINGS:
            res = "testfailed"
            text += res
        elif results in (EXCEPTION, RETRY):
            res = "exception"
            text += res
        else:
            res += "busted"
            text += res

        text += "\n";

        if self.columnName is None:
            # use the builder name
            text += "%s build: %s\n" % (t, name)
        elif type(self.columnName) is str:
            # use the exact string given
            text += "%s build: %s\n" % (t, self.columnName)
        elif isinstance(self.columnName, WithProperties):
            # interpolate the WithProperties instance, use that
            text += "%s build: %s\n" % (t, build.render(self.columnName))
        else:
            raise Exception("columnName is an unhandled value")
        text += "%s errorparser: %s\n" % (t, self.errorparser)

        # if the build just started...
        if results == "building":
            text += "%s END\n" % t
        # if the build finished...
        else:
            text += "%s binaryurl: %s\n" % (t, self.binaryURL)
            text += "%s logcompression: %s\n" % (t, self.logCompression)

            # logs will always be appended
            logEncoding = ""
            tinderboxLogs = ""
            for bs in build.getSteps():
                # Make sure that shortText is a regular string, so that bad
                # data in the logs don't generate UnicodeDecodeErrors
                shortText = "%s\n" % ' '.join(bs.getText()).encode('ascii', 'replace')

                # ignore steps that haven't happened
                if not re.match(".*[^\s].*", shortText):
                    continue
                # we ignore TinderboxPrint's here so we can do things like:
                # ShellCommand(command=['echo', 'TinderboxPrint:', ...])
                if re.match(".+TinderboxPrint.*", shortText):
                    shortText = shortText.replace("TinderboxPrint",
                                                  "Tinderbox Print")
                logs = bs.getLogs()

                tinderboxLogs += "======== BuildStep started ========\n"
                tinderboxLogs += shortText
                tinderboxLogs += "=== Output ===\n"
                for log in logs:
                    logText = log.getTextWithHeaders()
                    # Because we pull in the log headers here we have to ignore
                    # some of them. Basically, if we're TinderboxPrint'ing in
                    # a ShellCommand, the only valid one(s) are at the start
                    # of a line. The others are prendeded by whitespace, quotes,
                    # or brackets/parentheses
                    for line in logText.splitlines():
                        if re.match(".+TinderboxPrint.*", line):
                            line = line.replace("TinderboxPrint",
                                                "Tinderbox Print")
                        tinderboxLogs += line + "\n"

                tinderboxLogs += "=== Output ended ===\n"
                tinderboxLogs += "======== BuildStep ended ========\n"

            if self.logCompression == "bzip2":
                cLog = bz2.compress(tinderboxLogs)
                tinderboxLogs = base64.encodestring(cLog)
                logEncoding = "base64"
            elif self.logCompression == "gzip":
                cLog = cStringIO.StringIO()
                gz = gzip.GzipFile(mode="w", fileobj=cLog)
                gz.write(tinderboxLogs)
                gz.close()
                cLog = cLog.getvalue()
                tinderboxLogs = base64.encodestring(cLog)
                logEncoding = "base64"

            text += "%s logencoding: %s\n" % (t, logEncoding)
            text += "%s END\n\n" % t
            text += tinderboxLogs
            text += "\n"

        m = Message()
        m.set_payload(text)

        m['Date'] = formatdate(localtime=True)
        m['Subject'] = self.subject % { 'result': res,
                                        'builder': name,
                                        }
        m['From'] = self.fromaddr
        # m['To'] is added later

        d = defer.DeferredList([])
        d.addCallback(self._gotRecipients, self.extraRecipients, m)
        return d

