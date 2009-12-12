# -*- test-case-name: buildbot.test.test_mailparse -*-

"""
Parse various kinds of 'CVS notify' email.
"""
import os, re
import time, calendar
from email import message_from_file
from email.Utils import parseaddr
from email.Iterators import body_line_iterator

from zope.interface import implements
from twisted.python import log
from buildbot import util
from buildbot.interfaces import IChangeSource
from buildbot.changes import changes
from buildbot.changes.maildir import MaildirService

class MaildirSource(MaildirService, util.ComparableMixin):
    """This source will watch a maildir that is subscribed to a FreshCVS
    change-announcement mailing list.
    """
    implements(IChangeSource)

    compare_attrs = ["basedir", "pollinterval", "prefix"]
    name = None

    def __init__(self, maildir, prefix=None):
        MaildirService.__init__(self, maildir)
        self.prefix = prefix
        if prefix and not prefix.endswith("/"):
            log.msg("%s: you probably want your prefix=('%s') to end with "
                    "a slash")

    def describe(self):
        return "%s mailing list in maildir %s" % (self.name, self.basedir)

    def messageReceived(self, filename):
        path = os.path.join(self.basedir, "new", filename)
        change = self.parse_file(open(path, "r"), self.prefix)
        if change:
            self.parent.addChange(change)
        os.rename(os.path.join(self.basedir, "new", filename),
                  os.path.join(self.basedir, "cur", filename))

    def parse_file(self, fd, prefix=None):
        m = message_from_file(fd)
        return self.parse(m, prefix)

class FCMaildirSource(MaildirSource):
    name = "FreshCVS"

    def parse(self, m, prefix=None):
        """Parse mail sent by FreshCVS"""

        # FreshCVS sets From: to "user CVS <user>", but the <> part may be
        # modified by the MTA (to include a local domain)
        name, addr = parseaddr(m["from"])
        if not name:
            return None # no From means this message isn't from FreshCVS
        cvs = name.find(" CVS")
        if cvs == -1:
            return None # this message isn't from FreshCVS
        who = name[:cvs]

        # we take the time of receipt as the time of checkin. Not correct,
        # but it avoids the out-of-order-changes issue. See the comment in
        # parseSyncmail about using the 'Date:' header
        when = util.now()

        files = []
        comments = ""
        isdir = 0
        lines = list(body_line_iterator(m))
        while lines:
            line = lines.pop(0)
            if line == "Modified files:\n":
                break
        while lines:
            line = lines.pop(0)
            if line == "\n":
                break
            line = line.rstrip("\n")
            linebits = line.split(None, 1)
            file = linebits[0]
            if prefix:
                # insist that the file start with the prefix: FreshCVS sends
                # changes we don't care about too
                if file.startswith(prefix):
                    file = file[len(prefix):]
                else:
                    continue
            if len(linebits) == 1:
                isdir = 1
            elif linebits[1] == "0 0":
                isdir = 1
            files.append(file)
        while lines:
            line = lines.pop(0)
            if line == "Log message:\n":
                break
        # message is terminated by "ViewCVS links:" or "Index:..." (patch)
        while lines:
            line = lines.pop(0)
            if line == "ViewCVS links:\n":
                break
            if line.find("Index: ") == 0:
                break
            comments += line
        comments = comments.rstrip() + "\n"

        if not files:
            return None

        change = changes.Change(who, files, comments, isdir, when=when)

        return change

class SyncmailMaildirSource(MaildirSource):
    name = "Syncmail"

    def parse(self, m, prefix=None):
        """Parse messages sent by the 'syncmail' program, as suggested by the
        sourceforge.net CVS Admin documentation. Syncmail is maintained at
        syncmail.sf.net .
        """
        # pretty much the same as freshcvs mail, not surprising since CVS is
        # the one creating most of the text

        # The mail is sent from the person doing the checkin. Assume that the
        # local username is enough to identify them (this assumes a one-server
        # cvs-over-rsh environment rather than the server-dirs-shared-over-NFS
        # model)
        name, addr = parseaddr(m["from"])
        if not addr:
            return None # no From means this message isn't from FreshCVS
        at = addr.find("@")
        if at == -1:
            who = addr # might still be useful
        else:
            who = addr[:at]

        # we take the time of receipt as the time of checkin. Not correct (it
        # depends upon the email latency), but it avoids the
        # out-of-order-changes issue. Also syncmail doesn't give us anything
        # better to work with, unless you count pulling the v1-vs-v2
        # timestamp out of the diffs, which would be ugly. TODO: Pulling the
        # 'Date:' header from the mail is a possibility, and
        # email.Utils.parsedate_tz may be useful. It should be configurable,
        # however, because there are a lot of broken clocks out there.
        when = util.now()

        subject = m["subject"]
        # syncmail puts the repository-relative directory in the subject:
        # mprefix + "%(dir)s %(file)s,%(oldversion)s,%(newversion)s", where
        # 'mprefix' is something that could be added by a mailing list
        # manager.
        # this is the only reasonable way to determine the directory name
        space = subject.find(" ")
        if space != -1:
            directory = subject[:space]
        else:
            directory = subject

        files = []
        comments = ""
        isdir = 0
        branch = None

        lines = list(body_line_iterator(m))
        while lines:
            line = lines.pop(0)

            if (line == "Modified Files:\n" or
                line == "Added Files:\n" or
                line == "Removed Files:\n"):
                break

        while lines:
            line = lines.pop(0)
            if line == "\n":
                break
            if line == "Log Message:\n":
                lines.insert(0, line)
                break
            line = line.lstrip()
            line = line.rstrip()
            # note: syncmail will send one email per directory involved in a
            # commit, with multiple files if they were in the same directory.
            # Unlike freshCVS, it makes no attempt to collect all related
            # commits into a single message.

            # note: syncmail will report a Tag underneath the ... Files: line
            # e.g.:       Tag: BRANCH-DEVEL

            if line.startswith('Tag:'):
                branch = line.split(' ')[-1].rstrip()
                continue

            thesefiles = line.split(" ")
            for f in thesefiles:
                f = directory + "/" + f
                if prefix:
                    # insist that the file start with the prefix: we may get
                    # changes we don't care about too
                    if f.startswith(prefix):
                        f = f[len(prefix):]
                    else:
                        continue
                        break
                # TODO: figure out how new directories are described, set
                # .isdir
                files.append(f)

        if not files:
            return None

        while lines:
            line = lines.pop(0)
            if line == "Log Message:\n":
                break
        # message is terminated by "Index:..." (patch) or "--- NEW FILE.."
        # or "--- filename DELETED ---". Sigh.
        while lines:
            line = lines.pop(0)
            if line.find("Index: ") == 0:
                break
            if re.search(r"^--- NEW FILE", line):
                break
            if re.search(r" DELETED ---$", line):
                break
            comments += line
        comments = comments.rstrip() + "\n"

        change = changes.Change(who, files, comments, isdir, when=when,
                                branch=branch)

        return change

# Bonsai mail parser by Stephen Davis.
#
# This handles changes for CVS repositories that are watched by Bonsai
# (http://www.mozilla.org/bonsai.html)

# A Bonsai-formatted email message looks like:
# 
# C|1071099907|stephend|/cvs|Sources/Scripts/buildbot|bonsai.py|1.2|||18|7
# A|1071099907|stephend|/cvs|Sources/Scripts/buildbot|master.cfg|1.1|||18|7
# R|1071099907|stephend|/cvs|Sources/Scripts/buildbot|BuildMaster.py|||
# LOGCOMMENT
# Updated bonsai parser and switched master config to buildbot-0.4.1 style.
# 
# :ENDLOGCOMMENT
#
# In the first example line, stephend is the user, /cvs the repository,
# buildbot the directory, bonsai.py the file, 1.2 the revision, no sticky
# and branch, 18 lines added and 7 removed. All of these fields might not be
# present (during "removes" for example).
#
# There may be multiple "control" lines or even none (imports, directory
# additions) but there is one email per directory. We only care about actual
# changes since it is presumed directory additions don't actually affect the
# build. At least one file should need to change (the makefile, say) to
# actually make a new directory part of the build process. That's my story
# and I'm sticking to it.

class BonsaiMaildirSource(MaildirSource):
    name = "Bonsai"

    def parse(self, m, prefix=None):
        """Parse mail sent by the Bonsai cvs loginfo script."""

        # we don't care who the email came from b/c the cvs user is in the
        # msg text

        who = "unknown"
        timestamp = None
        files = []
        lines = list(body_line_iterator(m))

        # read the control lines (what/who/where/file/etc.)
        while lines:
            line = lines.pop(0)
            if line == "LOGCOMMENT\n":
                break;
            line = line.rstrip("\n")

            # we'd like to do the following but it won't work if the number of
            # items doesn't match so...
            #   what, timestamp, user, repo, module, file = line.split( '|' )
            items = line.split('|')
            if len(items) < 6:
                # not a valid line, assume this isn't a bonsai message
                return None

            try:
                # just grab the bottom-most timestamp, they're probably all the
                # same. TODO: I'm assuming this is relative to the epoch, but
                # this needs testing.
                timestamp = int(items[1])
            except ValueError:
                pass

            user = items[2]
            if user:
                who = user

            module = items[4]
            file = items[5]
            if module and file:
                path = "%s/%s" % (module, file)
                files.append(path)
            sticky = items[7]
            branch = items[8]

        # if no files changed, return nothing
        if not files:
            return None

        # read the comments
        comments = ""
        while lines:
            line = lines.pop(0)
            if line == ":ENDLOGCOMMENT\n":
                break
            comments += line
        comments = comments.rstrip() + "\n"

        # return buildbot Change object
        return changes.Change(who, files, comments, when=timestamp,
                              branch=branch)

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
            return None # no From means this message isn't from FreshCVS
        at = addr.find("@")
        if at == -1:
            who = addr # might still be useful
        else:
            who = addr[:at]

        # we take the time of receipt as the time of checkin. Not correct (it
        # depends upon the email latency), but it avoids the
        # out-of-order-changes issue. Also syncmail doesn't give us anything
        # better to work with, unless you count pulling the v1-vs-v2
        # timestamp out of the diffs, which would be ugly. TODO: Pulling the
        # 'Date:' header from the mail is a possibility, and
        # email.Utils.parsedate_tz may be useful. It should be configurable,
        # however, because there are a lot of broken clocks out there.
        when = util.now()

        files = []
        comments = ""
        isdir = 0
        lines = list(body_line_iterator(m))
        rev = None
        while lines:
            line = lines.pop(0)

            # "Author: jmason"
            match = re.search(r"^Author: (\S+)", line)
            if match:
                who = match.group(1)

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

        return changes.Change(who, files, comments, when=when, revision=rev)

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
#   To unsubscribe from this branch go to https://code.launchpad.net/~knielsen/maria/tmp-buildbot-test/+edit-subscription.
# 
# [end of mail]

class BzrLaunchpadEmailMaildirSource(MaildirSource):
    name = "Launchpad"

    compare_attrs = MaildirSource.compare_attrs + ["branchMap", "defaultBranch"]

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
        d = { 'files': [], 'comments': "" }
        gobbler = None
        rev = None
        who = None
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
                d['files'].append('%s RENAMED %s' % (match.group(1), match.group(2)))
            else:
                d['files'].append('%s RENAMED' % s)

        lines = list(body_line_iterator(m, True))
        rev = None
        while lines:
            line = lines.pop(0)

            # revno: 101
            match = re.search(r"^revno: ([0-9.]+)", line)
            if match:
                rev = match.group(1)

            # committer: Joe <joe@acme.com>
            match = re.search(r"^committer: (.*)$", line)
            if match:
                who = match.group(1)

            # timestamp: Fri 2009-05-15 10:35:43 +0200
            # datetime.strptime() is supposed to support %z for time zone, but
            # it does not seem to work. So handle the time zone manually.
            match = re.search(r"^timestamp: [a-zA-Z]{3} (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) ([-+])(\d{2})(\d{2})$", line)
            if match:
                datestr = match.group(1)
                tz_sign = match.group(2)
                tz_hours = match.group(3)
                tz_minutes = match.group(4)
                when = parseLaunchpadDate(datestr, tz_sign, tz_hours, tz_minutes)

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
                gobbler(line[2:-1]) # Use :-1 to gobble trailing newline

        # Determine the name of the branch.
        branch = None
        if self.branchMap and repository:
            if self.branchMap.has_key(repository):
                branch = self.branchMap[repository]
            elif self.branchMap.has_key('lp:' + repository):
                branch = self.branchMap['lp:' + repository]
        if not branch:
            if self.defaultBranch:
                branch = self.defaultBranch
            else:
                if repository:
                    branch = 'lp:' + repository
                else:
                    branch = None

        #log.msg("parse(): rev=%s who=%s files=%s comments='%s' when=%s branch=%s" % (rev, who, d['files'], d['comments'], time.asctime(time.localtime(when)), branch))
        if rev and who:
            return changes.Change(who, d['files'], d['comments'],
                                  when=when, revision=rev, branch=branch)
        else:
            return None

def parseLaunchpadDate(datestr, tz_sign, tz_hours, tz_minutes):
    time_no_tz = calendar.timegm(time.strptime(datestr, "%Y-%m-%d %H:%M:%S"))
    tz_delta = 60 * 60 * int(tz_sign + tz_hours) + 60 * int(tz_minutes)
    return time_no_tz - tz_delta
