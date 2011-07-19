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

import time, os
from xml.dom import minidom

from twisted.python import log
from twisted.internet import defer
from twisted.web.client import getPage

from buildbot.changes import base
from buildbot.util import epoch2datetime

class HgPoller(base.PollingChangeSource):
    """This source will poll a Mercurial server over HTTP using
    the pushlog RSS feed for changes and submit them to the
    change master."""

    compare_attrs = ['repourl', 'branch', 'pollInterval', 'project',
                     'category', 'workdir']

    def __init__(self, repourl, branch=None, branchType='dirname', workdir=None,
                 pollinterval=-2, project=None, category=None):

        if pollinterval != -2:
            pollInterval = pollinterval
        
        self.repourl = repourl
        self.branch = branch
        self.pollInterval = pollInterval
        self.workdir = workdir
        self.project = project
        self.working = False
        self.project = project or ''
        self.branchType = branchType
        if self.branchType == 'dirname':
            assert branch is not None
            self.branch = branch
        else:
            # pushlog is not branch-aware.
            self.branch = ''
        self.category = category

    def describe(self):
        return "hgpoller: watching %s" % self.repourl

    def getLastPoll(self):
        # if we don't set lastChange value to time of last poll it'll not find
        # the changes between and last poll in case maste stops.
        pollfile = self.workdir+os.sep+'lastpoll'
        timestamp = int(time.mktime(time.gmtime()))
        if os.path.exists(pollfile):
            f = open(pollfile, 'r')
            tstamp = f.read().strip()
            if len(tstamp) != 10:
                log.msg("Wrong timestamp stored, setting to current time")

            else:
                timestamp = int(tstamp)
            f.close()
        return timestamp

    def putLastPoll(self, res):
        pollfile = self.workdir+os.sep+'lastpoll'
        f = open(pollfile, 'w')
        timestamp = int(time.mktime(time.gmtime()))
        f.write(str(timestamp))
        f.close()
        return res

    def startService(self):
        if self.workdir is None:
            workdir = 'hgpoller-workdir'
        elif not os.path.isabs(self.workdir):
            workdir = self.workdir
        self.workdir = os.path.join(self.master.basedir, workdir)

        if not os.path.exists(self.workdir):
            log.msg('hgpoller: creating parent directories for workdir')
            os.makedirs(self.workdir)
        else:
            log.msg('hgpoller workdir already exists')

        self.lastPoll = self.lastChange = self.getLastPoll()
        base.PollingChangeSource.startService(self)

    def poll(self):
        if self.working:
            log.msg("Not polling because last poll is still working")
        else:
            self.working = True
            d = self._getChanges()
            d.addCallback(self.putLastPoll)
            d.addCallback(self.processChanges)
            d.addCallbacks(self.finishedOk, self.finishedFailure)

    def _makeURL(self):
        if not self.repourl.endswith('/'):
            self.repourl += '/'
        if self.branchType == 'dirname':
            return "%s%s/pushlog" % (self.repourl, self.branch)
        else:
            return "%spushlog" % (self.repourl)

    def _getChanges(self):
        url = self._makeURL()
        log.msg("Polling Hg server at %s" % url)
        return getPage(url)

    def finishedOk(self, res):
        assert self.working
        self.working = False
        return res

    def finishedFailure(self, res):
        log.msg("Hg poll failed: %s" % res)
        assert self.working
        self.working = False
        return None

    def _parseDate(self, dateString):
        # this is sensitive to dateString format.
        # No need to change this untill date format in pushlog is not changed
        # taken from http://wiki.python.org/moin/WorkingWithTime
        return time.mktime(time.strptime(dateString, "%Y-%m-%dT%H:%M:%SZ"))

    def _parseChanges(self, query):
        dom = minidom.parseString(query)
        items = dom.getElementsByTagName("entry")
        changes = []
        for i in items:
            d = {}
            for k in ["title", "updated"]:
                d[k] = i.getElementsByTagName(k)[0].firstChild.wholeText
            d["updated"] = self._parseDate(d["updated"])
            d["changeset"] = d["title"].split(" ")[1]
            nameNode = i.getElementsByTagName("author")[0].childNodes[1]
            d["author"] = nameNode.firstChild.wholeText
            d["link"] = i.getElementsByTagName("link")[0].getAttribute("href")
            files = []
            node = i.getElementsByTagName("content")[0]
            filesNode = node.childNodes[1].childNodes[1].childNodes # ugly
            for f in filesNode:
                files.append(f.firstChild.wholeText)
            d["files"] = files
            changes.append(d)
        changes = [c for c in changes if c['updated'] > self.lastChange]
        changes.reverse()
        return changes
    
    @defer.deferredGenerator
    def processChanges(self, query):
        change_list = self._parseChanges(query)
        for change in change_list:
            adjustedChangeTime = epoch2datetime(change["updated"])
            d = self.master.addChange(files = change["files"],
                                      author=change["author"],
                                      revision = change["changeset"],
                                      comments = change["link"],
                                      when_timestamp = adjustedChangeTime,
                                      branch = self.branch,
                                      # works only for dirname repos
                                      project = self.project,
                                      category = self.category)
            wfd = defer.waitForDeferred(d)
            yield wfd
            wfd.getResult()

        if len(change_list) > 0:
            self.lastChange = max(self.lastChange, *[c["updated"] for c in
                                                     change_list])
        else:
            log.msg("Hg poller: No changes found")
