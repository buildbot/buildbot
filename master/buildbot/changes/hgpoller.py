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

import time
import tempfile
import os
from twisted.python import log
from twisted.internet import defer, utils

from buildbot import config
from buildbot.util import deferredLocked
from buildbot.changes import base
from buildbot.util import epoch2datetime

class HgPoller(base.PollingChangeSource):
    """This source will poll a remote hg repo for changes and submit
    them to the change master."""

    compare_attrs = ["repourl", "branch", "workdir",
                     "pollInterval", "hgpoller", "usetimestamps",
                     "category", "project"]

    db_class_name = 'HgPoller'

    def __init__(self, repourl, branch='default',
                 workdir=None, pollInterval=10*60,
                 hgbin='hg', usetimestamps=True,
                 category=None, project='',
                 encoding='utf-8'):

        self.repourl = repourl
        self.branch = branch
        self.pollInterval = pollInterval
        self.encoding = encoding
        self.lastChange = time.time()
        self.lastPoll = time.time()
        self.hgbin = hgbin
        self.workdir = workdir
        self.usetimestamps = usetimestamps
        self.category = category
        self.project = project
        self.changeCount = 0
        self.commitInfo  = {}
        self.initLock = defer.DeferredLock()

        if self.workdir == None:
            config.error("workdir is mandatory for now in HgPoller")

    def startService(self):
        # make our workdir absolute, relative to the master's basedir
        if not os.path.isabs(self.workdir):
            self.workdir = os.path.join(self.master.basedir, self.workdir)
            log.msg("hgpoller: using workdir '%s'" % self.workdir)

        # initialize the repository we'll use to get changes; note that
        # startService is not an event-driven method, so this method will
        # instead acquire self.initLock immediately when it is called.
        if not os.path.exists(self.workdir + r'/.hg'):
            d = self.initRepository()
            d.addErrback(log.err, 'while initializing HgPoller repository')
        else:
            log.msg("HgPoller repository already exists")

        # call this *after* initRepository, so that the initLock is locked first
        base.PollingChangeSource.startService(self)

    @deferredLocked('initLock')
    def initRepository(self):
        d = defer.succeed(None)
        def make_dir(_):
            dirpath = os.path.dirname(self.workdir.rstrip(os.sep))
            if not os.path.exists(dirpath):
                log.msg('hgpoller: creating parent directories for workdir')
                os.makedirs(dirpath)
        d.addCallback(make_dir)

        def hg_init(_):
            log.msg('hgpoller: initializing working dir from %s' % self.repourl)
            d = utils.getProcessOutputAndValue(self.hgbin,
                    ['init', self.workdir], env=os.environ)
            d.addCallback(self._convert_nonzero_to_failure)
            d.addErrback(self._stop_on_failure)
            return d
        d.addCallback(hg_init)

        def msg(_):
            log.msg(
                "hgpoller: finished initializing working dir %r" % self.workdir)

        d.addCallback(msg)
        return d

    def describe(self):
        status = ""
        if not self.master:
            status = "[STOPPED - check log]"
        return ("HgPoller watching the remote Mercurial repository %s, "
                "branch: %s %s") % (self.repourl, self.branch, status)

    @deferredLocked('initLock')
    def poll(self):
        d = self._get_changes()
        d.addCallback(self._process_changes)
        d.addErrback(self._process_changes_failure)
        return d

    def _get_rev_details(self, rev):
        """Return a deferred for (date, author, files, comments) of given rev.

        Deferred will be in error if rev is unknown.
        """
        args = ['log', '-r', rev, os.linesep.join((
            '--template={date|hgdate}',
            '{author}',
            '{files}',
            '{desc|strip}'))]
        # Mercurial fails with status 255 if rev is unknown
        d = utils.getProcessOutput(self.hgbin, args, path=self.workdir,
                                   env=os.environ, errortoo=False )
        def process(output):
            # fortunately, Mercurial issues all filenames one one line
            date, author, files, comments = output.decode(self.encoding).split(
                os.linesep, 3)

            if not self.usetimestamps:
                stamp = None
            else:
                try:
                    stamp = sum(float(d) for d in date.split())
                except:
                    log.msg('hgpoller: caught exception converting output %r '
                            'to timestamp' % date)
                    raise
            return stamp, author.strip(), files.split(), comments.strip()

        d.addCallback(process)
        return d

    def _get_changes(self):
        log.msg('hgpoller: polling hg repo at %s' % self.repourl)

        self.lastPoll = time.time()

        # get a deferred object that performs the fetch
        args = ['pull', '-b', self.branch, self.repourl]

        # This command always produces data on stderr, but we actually do not
        # care about the stderr or stdout from this command.
        # We set errortoo=True to avoid an errback from the deferred.
        # The callback which will be added to this
        # deferred will not use the response.
        d = utils.getProcessOutput(self.hgbin, args,
                    path=self.workdir,
                    env=os.environ, errortoo=True )

        return d

    def getStateObjectId(self):
        """Return a deferred for object id in state db.

        Being unique among pollers, workdir is used as instance name for db.
        """
        return self.master.db.state.getObjectId(self.workdir,
                                                self.db_class_name)

    def getCurrentRev(self):
        """Return a deferred for object id in state db and current numeric rev.

        If never has been set, current rev is None.
        """
        d = self.getStateObjectId()
        def oid_cb(oid):
            current = self.master.db.state.getState(oid, 'current_rev', None)
            def to_int(cur):
                return oid, cur and int(cur) or None
            current.addCallback(to_int)
            return current
        d.addCallback(oid_cb)
        return d

    def setCurrentRev(self, rev, oid=None):
        """Return a deferred to set current revision in persistent state.

        oid is self's id for state db. It can be passed to avoid a db lookup."""
        if oid is None:
            d = self.getStateObjectId()
        else:
            d = defer.succeed(oid)
        def set_in_state(obj_id):
            return self.master.db.state.setState(obj_id, 'current_rev', rev)

        d.addCallback(set_in_state)
        return d

    def getHead(self):
        """Return a deferred for branch head revision or None.

        We'll get an error if there is no head for this branch, which is
        proabably a good thing, since it's probably a mispelling
        (if really buildbotting a branch that does not have any changeset
        yet, one shouldn't be surprised to get errors)
        """
        d = utils.getProcessOutput(self.hgbin,
                    ['heads', self.branch, '--template={rev}' + os.linesep],
                    path=self.workdir, env=os.environ, errortoo=False)

        def no_head_err(exc):
            log.err("hgpoller: could not find branch %r in repository %r" % (
                self.branch, self.repourl))
        d.addErrback(no_head_err)

        def results(heads):
            if not heads:
                return

            if len(heads.split()) > 1:
                log.err(("hgpoller: caught several heads in branch %r "
                         "from repository %r. Staying at previous revision"
                         "You should wait until the situation is normal again "
                         "due to a merge or directly strip if remote repo "
                         "gets stripped later.") % (self.branch, self.repourl))
                return

            # in case of whole reconstruction, are we sure that we'll get the
            # same node -> rev assignations ?
            return int(heads.strip())

        d.addCallback(results)
        return d

    @defer.inlineCallbacks
    def _process_changes(self, unused_output):
        """Send info about pulled changes to the master and record current.

        GitPoller does the recording by moving the working dir to the head
        of the branch.
        We don't update the tree (unnecessary treatment and waste of space)
        instead, we simply store the current rev number in a file.
        Recall that hg rev numbers are local and incremental.
        """
        oid, current = yield self.getCurrentRev()
        # hg log on a range of revisions is never empty
        # also, if a numeric revision does not exist, a node may match.
        # Therefore, we have to check explicitely that branch head > current.
        head = yield self.getHead()
        if head <= current:
            return

        self.changeCount = 0
        if current is None:
            # we could have used current = -1 convention as well (as hg does)
            revrange = '0:%d' % head
        else:
            revrange = '%d:%s' % (current + 1, head)

        # two passes for hg log makes parsing simpler (comments is multi-lines)
        revListArgs = ['log', '-b', self.branch, '-r', revrange,
                       r'--template={rev}:{node}\n']
        results = yield utils.getProcessOutput(self.hgbin, revListArgs,
                    path=self.workdir, env=os.environ, errortoo=False )

        revNodeList = [rn.split(':', 1) for rn in results.strip().split()]
        self.changeCount = len(revNodeList)

        log.msg('hgpoller: processing %d changes: %r in %r'
                % (self.changeCount, revNodeList, self.workdir))
        for rev, node in revNodeList:
            timestamp, author, files, comments = yield self._get_rev_details(
                node)
            yield self.master.addChange(
                   author=author,
                   revision=node,
                   files=files,
                   comments=comments,
                   when_timestamp=epoch2datetime(timestamp),
                   branch=self.branch,
                   category=self.category,
                   project=self.project,
                   repository=self.repourl,
                   src='hg')
            # writing after addChange so that a rev is never missed,
            # but at once to avoid impact from later errors
            yield self.setCurrentRev(rev, oid=oid)

    def _process_changes_failure(self, f):
        log.msg('hgpoller: repo poll failed')
        log.err(f)
        # eat the failure to continue along the defered chain - we still want to catch up
        return None

    def _convert_nonzero_to_failure(self, res):
        "utility method to handle the result of getProcessOutputAndValue"
        (stdout, stderr, code) = res
        if code != 0:
            raise EnvironmentError('command failed with exit code %d: %s' % (code, stderr))
        return (stdout, stderr, code)

    def _stop_on_failure(self, f):
        "utility method to stop the service when a failure occurs"
        if self.running:
            d = defer.maybeDeferred(lambda : self.stopService())
            d.addErrback(log.err, 'while stopping broken HgPoller service')
        return f
