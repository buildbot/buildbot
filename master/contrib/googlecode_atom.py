# GoogleCode Atom Feed Poller
# Author: Srivats P. <pstavirs>
# Based on Mozilla's HgPoller
#     http://bonsai.mozilla.org/cvsblame.cgi?file=/mozilla/tools/buildbot/buildbot/changes/Attic/hgpoller.py&revision=1.1.4.2
#
# Description:
#   Use this ChangeSource for projects hosted on http://code.google.com/
#
#   This ChangeSource uses the project's commit Atom feed. Depending upon the
#   frequency of commits, you can tune the polling interval for the feed
#   (default is 1 hour)
#
# Parameters:
#   feedurl (MANDATORY): The Atom feed URL of the GoogleCode repo
#   pollinterval (OPTIONAL): Polling frequency for the feed (in seconds)
#
# Example:
# To poll the Ostinato project's commit feed every 3 hours, use -
#   from googlecode_atom import GoogleCodeAtomPoller
#   poller = GoogleCodeAtomPoller(
#            feedurl="http://code.google.com/feeds/p/ostinato/hgchanges/basic",
#            pollinterval=10800)
#   c['change_source'] = [ poller ]
#

from time import strptime
from calendar import timegm
from xml.dom import minidom, Node

from twisted.python import log, failure
from twisted.internet import defer, reactor
from twisted.internet.task import LoopingCall
from twisted.web.client import getPage

from buildbot.changes import base, changes

def googleCodePollerForProject(project, vcs, pollinterval=3600):
    return GoogleCodeAtomPoller(
        'http://code.google.com/feeds/p/%s/%schanges/basic' % (project, vcs),
        pollinterval=pollinterval)


class GoogleCodeAtomPoller(base.ChangeSource):
    """This source will poll a GoogleCode Atom feed for changes and
    submit them to the change master. Works for both Svn and Hg repos.
    TODO: branch processing
    """

    compare_attrs = ['feedurl', 'pollinterval']
    parent = None
    loop = None
    volatile = ['loop']
    working = False

    def __init__(self, feedurl, pollinterval=3600):
        """
        @type   feedurl:        string
        @param  feedurl:        The Atom feed URL of the GoogleCode repo
                                (e.g. http://code.google.com/feeds/p/ostinato/hgchanges/basic)

        @type   pollinterval:   int
        @param  pollinterval:   The time (in seconds) between queries for
                                changes (default is 1 hour)
        """

        self.feedurl = feedurl
        self.branch = None
        self.pollinterval = pollinterval
        self.lastChange = None
        self.loop = LoopingCall(self.poll)

    def startService(self):
        log.msg("GoogleCodeAtomPoller starting")
        base.ChangeSource.startService(self)
        reactor.callLater(0, self.loop.start, self.pollinterval)

    def stopService(self):
        log.msg("GoogleCodeAtomPoller stoppping")
        self.loop.stop()
        return base.ChangeSource.stopService(self)

    def describe(self):
        return ("Getting changes from the GoogleCode repo changes feed %s" %
               self._make_url())

    def poll(self):
        if self.working:
            log.msg("Not polling because last poll is still working")
        else:
            self.working = True
            d = self._get_changes()
            d.addCallback(self._process_changes)
            d.addCallbacks(self._finished_ok, self._finished_failure)

    def _finished_ok(self, res):
        assert self.working
        self.working = False
        log.msg("GoogleCodeAtomPoller poll success")

        return res

    def _finished_failure(self, res):
        log.msg("GoogleCodeAtomPoller poll failed: %s" % res)
        assert self.working
        self.working = False
        return None

    def _make_url(self):
        return "%s" % (self.feedurl)

    def _get_changes(self):
        url = self._make_url()
        log.msg("GoogleCodeAtomPoller polling %s" % url)

        return getPage(url, timeout=self.pollinterval)

    def _parse_changes(self, query):
        dom = minidom.parseString(query)
        entries = dom.getElementsByTagName("entry")
        changes = []
        # Entries come in reverse chronological order
        for i in entries:
            d = {}

            # revision is the last part of the 'id' url
            d["revision"] = i.getElementsByTagName(
                "id")[0].firstChild.data.split('/')[-1]
            if d["revision"] == self.lastChange:
                break  # no more new changes

            d["when"] = timegm(strptime(
                i.getElementsByTagName("updated")[0].firstChild.data,
                "%Y-%m-%dT%H:%M:%SZ"))
            d["author"] = i.getElementsByTagName(
                "author")[0].getElementsByTagName("name")[0].firstChild.data
            # files and commit msg are separated by 2 consecutive <br/>
            content = i.getElementsByTagName(
                "content")[0].firstChild.data.split("<br/>\n <br/>")
            # Remove the action keywords from the file list
            fl = content[0].replace(
                u' \xa0\xa0\xa0\xa0Add\xa0\xa0\xa0\xa0', '').replace(
                u' \xa0\xa0\xa0\xa0Delete\xa0\xa0\xa0\xa0', '').replace(
                u' \xa0\xa0\xa0\xa0Modify\xa0\xa0\xa0\xa0', '')
            # Get individual files and remove the 'header'
            d["files"] = fl.encode("ascii", "replace").split("<br/>")[1:]
            d["files"] = [f.strip() for f in d["files"]]
            try:
                d["comments"] = content[1].encode("ascii", "replace")
            except:
                d["comments"] = "No commit message provided"

            changes.append(d)

        changes.reverse() # want them in chronological order
        return changes

    def _process_changes(self, query):
        change_list = self._parse_changes(query)

        # Skip calling addChange() if this is the first successful poll.
        if self.lastChange is not None:
            for change in change_list:
                c = changes.Change(revision = change["revision"],
                                   who = change["author"],
                                   files = change["files"],
                                   comments = change["comments"],
                                   when = change["when"],
                                   branch = self.branch)
                self.parent.addChange(c)
        if change_list:
            self.lastChange = change_list[-1]["revision"]
