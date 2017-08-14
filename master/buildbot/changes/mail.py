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
Parse various kinds of 'CVS notify' email.
"""

from __future__ import absolute_import
from __future__ import print_function
from future.utils import text_type

import calendar
import datetime
import re
import time
from email import message_from_file
from email.iterators import body_line_iterator
from email.utils import mktime_tz
from email.utils import parseaddr
from email.utils import parsedate_tz

from twisted.internet import defer
from twisted.python import log
from zope.interface import implementer

from buildbot import util
from buildbot.interfaces import IChangeSource
from buildbot.util.maildir import MaildirService


@implementer(IChangeSource)
class MaildirSource(MaildirService, util.ComparableMixin):

    """Generic base class for Maildir-based change sources"""

    compare_attrs = ("basedir", "pollinterval", "prefix")

    def __init__(self, maildir, prefix=None, category='', repository=''):
        MaildirService.__init__(self, maildir)
        self.prefix = prefix
        self.category = category
        self.repository = repository
        if prefix and not prefix.endswith("/"):
            log.msg("%s: you probably want your prefix=('%s') to end with "
                    "a slash")

    def describe(self):
        return "%s watching maildir '%s'" % (self.__class__.__name__, self.basedir)

    def messageReceived(self, filename):
        d = defer.succeed(None)

        @d.addCallback
        def parse_file(_):
            with self.moveToCurDir(filename) as f:
                parsedFile = self.parse_file(f, self.prefix)
            return parsedFile

        @d.addCallback
        def add_change(chtuple):
            src, chdict = None, None
            if chtuple:
                src, chdict = chtuple
            if chdict:
                return self.master.data.updates.addChange(src=text_type(src),
                                                          **chdict)
            else:
                log.msg("no change found in maildir file '%s'" % filename)

        return d

    def parse_file(self, fd, prefix=None):
        m = message_from_file(fd)
        return self.parse(m, prefix)


class CVSMaildirSource(MaildirSource):
    name = "CVSMaildirSource"

    def __init__(self, maildir, prefix=None, category='',
                 repository='', properties=None):
        MaildirSource.__init__(self, maildir, prefix, category, repository)
        if properties is None:
            properties = {}
        self.properties = properties

    def parse(self, m, prefix=None):
        """Parse messages sent by the 'buildbot-cvs-mail' program.
        """
        # The mail is sent from the person doing the checkin. Assume that the
        # local username is enough to identify them (this assumes a one-server
        # cvs-over-rsh environment rather than the server-dirs-shared-over-NFS
        # model)
        name, addr = parseaddr(m["from"])
        if not addr:
            # no From means this message isn't from buildbot-cvs-mail
            return None
        at = addr.find("@")
        if at == -1:
            author = addr  # might still be useful
        else:
            author = addr[:at]
        author = util.ascii2unicode(author)

        # CVS accepts RFC822 dates. buildbot-cvs-mail adds the date as
        # part of the mail header, so use that.
        # This assumes cvs is being access via ssh or pserver, so the time
        # will be the CVS server's time.

        # calculate a "revision" based on that timestamp, or the current time
        # if we're unable to parse the date.
        log.msg('Processing CVS mail')
        dateTuple = parsedate_tz(m["date"])
        if dateTuple is None:
            when = util.now()
        else:
            when = mktime_tz(dateTuple)

        theTime = datetime.datetime.utcfromtimestamp(float(when))
        rev = theTime.strftime('%Y-%m-%d %H:%M:%S')

        catRE = re.compile(r'^Category:\s*(\S.*)')
        cvsRE = re.compile(r'^CVSROOT:\s*(\S.*)')
        cvsmodeRE = re.compile(r'^Cvsmode:\s*(\S.*)')
        filesRE = re.compile(r'^Files:\s*(\S.*)')
        modRE = re.compile(r'^Module:\s*(\S.*)')
        pathRE = re.compile(r'^Path:\s*(\S.*)')
        projRE = re.compile(r'^Project:\s*(\S.*)')
        singleFileRE = re.compile(r'(.*) (NONE|\d(\.|\d)+) (NONE|\d(\.|\d)+)')
        tagRE = re.compile(r'^\s+Tag:\s*(\S.*)')
        updateRE = re.compile(r'^Update of:\s*(\S.*)')
        comments = ""
        branch = None
        cvsroot = None
        fileList = None
        files = []
        isdir = 0
        path = None
        project = None

        lines = list(body_line_iterator(m))
        while lines:
            line = lines.pop(0)
            m = catRE.match(line)
            if m:
                category = m.group(1)
                continue
            m = cvsRE.match(line)
            if m:
                cvsroot = m.group(1)
                continue
            m = cvsmodeRE.match(line)
            if m:
                cvsmode = m.group(1)
                continue
            m = filesRE.match(line)
            if m:
                fileList = m.group(1)
                continue
            m = modRE.match(line)
            if m:
                # We don't actually use this
                # module = m.group(1)
                continue
            m = pathRE.match(line)
            if m:
                path = m.group(1)
                continue
            m = projRE.match(line)
            if m:
                project = m.group(1)
                continue
            m = tagRE.match(line)
            if m:
                branch = m.group(1)
                continue
            m = updateRE.match(line)
            if m:
                # We don't actually use this
                # updateof = m.group(1)
                continue
            if line == "Log Message:\n":
                break

        # CVS 1.11 lists files as:
        #   repo/path file,old-version,new-version file2,old-version,new-version
        # Version 1.12 lists files as:
        #   file1 old-version new-version file2 old-version new-version
        #
        # files consists of tuples of 'file-name old-version new-version'
        # The versions are either dotted-decimal version numbers, ie 1.1
        # or NONE. New files are of the form 'NONE NUMBER', while removed
        # files are 'NUMBER NONE'. 'NONE' is a literal string
        # Parsing this instead of files list in 'Added File:' etc
        # makes it possible to handle files with embedded spaces, though
        # it could fail if the filename was 'bad 1.1 1.2'
        # For cvs version 1.11, we expect
        #  my_module new_file.c,NONE,1.1
        #  my_module removed.txt,1.2,NONE
        #  my_module modified_file.c,1.1,1.2
        # While cvs version 1.12 gives us
        #  new_file.c NONE 1.1
        #  removed.txt 1.2 NONE
        #  modified_file.c 1.1,1.2

        if fileList is None:
            log.msg('CVSMaildirSource Mail with no files. Ignoring')
            return None       # We don't have any files. Email not from CVS

        if cvsmode == '1.11':
            # Please, no repo paths with spaces!
            m = re.search('([^ ]*) ', fileList)
            if m:
                path = m.group(1)
            else:
                log.msg(
                    'CVSMaildirSource can\'t get path from file list. Ignoring mail')
                return
            fileList = fileList[len(path):].strip()
            singleFileRE = re.compile(
                r'(.+?),(NONE|(?:\d+\.(?:\d+\.\d+\.)*\d+)),(NONE|(?:\d+\.(?:\d+\.\d+\.)*\d+))(?: |$)')
        elif cvsmode == '1.12':
            singleFileRE = re.compile(
                r'(.+?) (NONE|(?:\d+\.(?:\d+\.\d+\.)*\d+)) (NONE|(?:\d+\.(?:\d+\.\d+\.)*\d+))(?: |$)')
            if path is None:
                raise ValueError(
                    'CVSMaildirSource cvs 1.12 require path. Check cvs loginfo config')
        else:
            raise ValueError(
                'Expected cvsmode 1.11 or 1.12. got: %s' % cvsmode)

        log.msg("CVSMaildirSource processing filelist: %s" % fileList)
        while(fileList):
            m = singleFileRE.match(fileList)
            if m:
                curFile = path + '/' + m.group(1)
                files.append(curFile)
                fileList = fileList[m.end():]
            else:
                log.msg('CVSMaildirSource no files matched regex. Ignoring')
                return None   # bail - we couldn't parse the files that changed
        # Now get comments
        while lines:
            line = lines.pop(0)
            comments += line

        comments = comments.rstrip() + "\n"
        if comments == '\n':
            comments = None
        return ('cvs', dict(author=author, files=files, comments=comments,
                            isdir=isdir, when=when, branch=branch,
                            revision=rev, category=category,
                            repository=cvsroot, project=project,
                            properties=self.properties))

# svn "commit-email.pl" handler.  The format is very similar to freshcvs mail;
# here's a sample:

#  From: username [at] apache.org    [slightly obfuscated to avoid spam here]
#  To: commits [at] spamassassin.apache.org
#  Subject: svn commit: r105955 - in spamassassin/trunk: . lib/Mail
#  ...
#
#  Author: username
#  Date: Sat Nov 20 00:17:49 2004      [note: TZ = local tz on server!]
#  New Revision: 105955
#
#  Modified:   [also Removed: and Added:]
#    [filename]
#    ...
#  Log:
#  [log message]
#  ...
#
#
#  Modified: spamassassin/trunk/lib/Mail/SpamAssassin.pm
#  [unified diff]
#
#  [end of mail]


class SVNCommitEmailMaildirSource(MaildirSource):
    name = "SVN commit-email.pl"

    def parse(self, m, prefix=None):
        """Parse messages sent by the svn 'commit-email.pl' trigger.
        """

        # The mail is sent from the person doing the checkin. Assume that the
        # local username is enough to identify them (this assumes a one-server
        # cvs-over-rsh environment rather than the server-dirs-shared-over-NFS
        # model)
        name, addr = parseaddr(m["from"])
        if not addr:
            return None  # no From means this message isn't from svn
        at = addr.find("@")
        if at == -1:
            author = addr  # might still be useful
        else:
            author = addr[:at]

        # we take the time of receipt as the time of checkin. Not correct (it
        # depends upon the email latency), but it avoids the
        # out-of-order-changes issue. Also syncmail doesn't give us anything
        # better to work with, unless you count pulling the v1-vs-v2
        # timestamp out of the diffs, which would be ugly. TODO: Pulling the
        # 'Date:' header from the mail is a possibility, and
        # email.utils.parsedate_tz may be useful. It should be configurable,
        # however, because there are a lot of broken clocks out there.
        when = util.now()

        files = []
        comments = ""
        lines = list(body_line_iterator(m))
        rev = None
        while lines:
            line = lines.pop(0)

            # "Author: jmason"
            match = re.search(r"^Author: (\S+)", line)
            if match:
                author = match.group(1)

            # "New Revision: 105955"
            match = re.search(r"^New Revision: (\d+)", line)
            if match:
                rev = match.group(1)

            # possible TODO: use "Date: ..." data here instead of time of
            # commit message receipt, above. however, this timestamp is
            # specified *without* a timezone, in the server's local TZ, so to
            # be accurate buildbot would need a config setting to specify the
            # source server's expected TZ setting! messy.

            # this stanza ends with the "Log:"
            if (line == "Log:\n"):
                break

        # commit message is terminated by the file-listing section
        while lines:
            line = lines.pop(0)
            if (line == "Modified:\n" or
                line == "Added:\n" or
                    line == "Removed:\n"):
                break
            comments += line
        comments = comments.rstrip() + "\n"

        while lines:
            line = lines.pop(0)
            if line == "\n":
                break
            if line.find("Modified:\n") == 0:
                continue            # ignore this line
            if line.find("Added:\n") == 0:
                continue            # ignore this line
            if line.find("Removed:\n") == 0:
                continue            # ignore this line
            line = line.strip()

            thesefiles = line.split(" ")
            for f in thesefiles:
                if prefix:
                    # insist that the file start with the prefix: we may get
                    # changes we don't care about too
                    if f.startswith(prefix):
                        f = f[len(prefix):]
                    else:
                        log.msg("ignored file from svn commit: prefix '%s' "
                                "does not match filename '%s'" % (prefix, f))
                        continue

                # TODO: figure out how new directories are described, set
                # .isdir
                files.append(f)

        if not files:
            log.msg("no matching files found, ignoring commit")
            return None

        return ('svn', dict(author=author, files=files, comments=comments,
                            when=when, revision=rev))

# bzr Launchpad branch subscription mails. Sample mail:
#
#   From: noreply@launchpad.net
#   Subject: [Branch ~knielsen/maria/tmp-buildbot-test] Rev 2701: test add file
#   To: Joe <joe@acme.com>
#   ...
#
#   ------------------------------------------------------------
#   revno: 2701
#   committer: Joe <joe@acme.com>
#   branch nick: tmpbb
#   timestamp: Fri 2009-05-15 10:35:43 +0200
#   message:
#     test add file
#   added:
#     test-add-file
#
#
#   --
#
#   https://code.launchpad.net/~knielsen/maria/tmp-buildbot-test
#
#   You are subscribed to branch lp:~knielsen/maria/tmp-buildbot-test.
#   To unsubscribe from this branch go to
#   https://code.launchpad.net/~knielsen/maria/tmp-buildbot-test/+edit-subscription.
#
# [end of mail]


class BzrLaunchpadEmailMaildirSource(MaildirSource):
    name = "Launchpad"

    compare_attrs = ("branchMap", "defaultBranch")

    def __init__(self, maildir, prefix=None, branchMap=None, defaultBranch=None, **kwargs):
        self.branchMap = branchMap
        self.defaultBranch = defaultBranch
        MaildirSource.__init__(self, maildir, prefix, **kwargs)

    def parse(self, m, prefix=None):
        """Parse branch notification messages sent by Launchpad.
        """

        subject = m["subject"]
        match = re.search(r"^\s*\[Branch\s+([^]]+)\]", subject)
        if match:
            repository = match.group(1)
        else:
            repository = None

        # Put these into a dictionary, otherwise we cannot assign them
        # from nested function definitions.
        d = {'files': [], 'comments': u""}
        gobbler = None
        rev = None
        author = None
        when = util.now()

        def gobble_comment(s):
            d['comments'] += s + "\n"

        def gobble_removed(s):
            d['files'].append('%s REMOVED' % s)

        def gobble_added(s):
            d['files'].append('%s ADDED' % s)

        def gobble_modified(s):
            d['files'].append('%s MODIFIED' % s)

        def gobble_renamed(s):
            match = re.search(r"^(.+) => (.+)$", s)
            if match:
                d['files'].append('%s RENAMED %s' %
                                  (match.group(1), match.group(2)))
            else:
                d['files'].append('%s RENAMED' % s)

        lines = list(body_line_iterator(m, True))
        rev = None
        while lines:
            line = text_type(lines.pop(0), "utf-8", errors="ignore")

            # revno: 101
            match = re.search(r"^revno: ([0-9.]+)", line)
            if match:
                rev = match.group(1)

            # committer: Joe <joe@acme.com>
            match = re.search(r"^committer: (.*)$", line)
            if match:
                author = match.group(1)

            # timestamp: Fri 2009-05-15 10:35:43 +0200
            # datetime.strptime() is supposed to support %z for time zone, but
            # it does not seem to work. So handle the time zone manually.
            match = re.search(
                r"^timestamp: [a-zA-Z]{3} (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) ([-+])(\d{2})(\d{2})$", line)
            if match:
                datestr = match.group(1)
                tz_sign = match.group(2)
                tz_hours = match.group(3)
                tz_minutes = match.group(4)
                when = parseLaunchpadDate(
                    datestr, tz_sign, tz_hours, tz_minutes)

            if re.search(r"^message:\s*$", line):
                gobbler = gobble_comment
            elif re.search(r"^removed:\s*$", line):
                gobbler = gobble_removed
            elif re.search(r"^added:\s*$", line):
                gobbler = gobble_added
            elif re.search(r"^renamed:\s*$", line):
                gobbler = gobble_renamed
            elif re.search(r"^modified:\s*$", line):
                gobbler = gobble_modified
            elif re.search(r"^  ", line) and gobbler:
                gobbler(line[2:-1])  # Use :-1 to gobble trailing newline

        # Determine the name of the branch.
        branch = None
        if self.branchMap and repository:
            if repository in self.branchMap:
                branch = self.branchMap[repository]
            elif ("lp:" + repository) in self.branchMap:
                branch = self.branchMap['lp:' + repository]
        if not branch:
            if self.defaultBranch:
                branch = self.defaultBranch
            else:
                if repository:
                    branch = 'lp:' + repository
                else:
                    branch = None

        if rev and author:
            return ('bzr', dict(author=author, files=d['files'],
                                comments=d['comments'],
                                when=when, revision=rev,
                                branch=branch, repository=repository or ''))
        return None


def parseLaunchpadDate(datestr, tz_sign, tz_hours, tz_minutes):
    time_no_tz = calendar.timegm(time.strptime(datestr, "%Y-%m-%d %H:%M:%S"))
    tz_delta = 60 * 60 * int(tz_sign + tz_hours) + 60 * int(tz_minutes)
    return time_no_tz - tz_delta
