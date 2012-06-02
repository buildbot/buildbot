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

from buildbot.util import deferredLocked
from buildbot.changes import base
from buildbot.util import epoch2datetime

class HgPoller(base.PollingChangeSource):
    """This source will poll a remote hg repo for changes and submit
    them to the change master."""

    compare_attrs = ["repourl", "branch", "workdir",
                     "pollInterval", "hgpoller", "usetimestamps",
                     "category", "project"]

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
            # GR TODO no need of deprecation for a brand new poller
            # find out what to raise instead
            self.workdir = tempfile.gettempdir() + '/hgpoller_work'
            log.msg("WARNING: hgpoller using deprecated temporary workdir " +
                    "'%s'; consider setting workdir=" % self.workdir)

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

        def hg_pull_branch(_):
            """Pull only changesets from the branch we're interested in."""
            args = ['pull', '-b', self.branch, self.repourl]
            d = utils.getProcessOutputAndValue(self.hgbin, args,
                    path=self.workdir, env=os.environ)
            d.addCallback(self._convert_nonzero_to_failure)
            d.addErrback(self._stop_on_failure)
            return d
        d.addCallback(hg_pull_branch)

        def get_rev(_):
            # GR TODO: we may have several heads
            # raise ? what then ?
            # take the first ?
            d = utils.getProcessOutputAndValue(self.hgbin,
                    ['--template={node}', 'heads', self.branch],
                    path=self.workdir, env=os.environ)
            d.addCallback(self._convert_nonzero_to_failure)
            d.addErrback(self._stop_on_failure)
            d.addCallback(lambda (out, err, code) : out.strip())
            return d
        d.addCallback(get_rev)

        def print_rev(rev):
            log.msg("hgpoller: finished initializing working dir from %s at rev %s"
                    % (self.repourl, rev))
        d.addCallback(print_rev)
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

    def _get_commit_comments(self, rev):
        args = ['log', '-r', rev, r'--template={desc|strip}\n']
        d = utils.getProcessOutput(self.hgbin, args, path=self.workdir, env=os.environ, errortoo=False )
        def process(git_output):
            stripped_output = git_output.strip().decode(self.encoding)
            if len(stripped_output) == 0:
                raise EnvironmentError('could not get commit comment for rev')
            return stripped_output
        d.addCallback(process)
        return d

    def _get_commit_timestamp(self, rev):
        # unix timestamp
        args = ['log', '-r', rev, '--template={date|hgdate}']
        d = utils.getProcessOutput(self.hgbin, args, path=self.workdir, env=os.environ, errortoo=False )
        def process(output):
            """hgdate format is 'seconds correction_to_utc'."""
            output = output.strip()
            if self.usetimestamps:
                try:
                    stamp = sum(float(d) for d in output.split())
                except Exception, e:
                        log.msg('hgpoller: caught exception converting output \'%s\' to timestamp' % stripped_output)
                        raise e
                return stamp
            else:
                return None
        d.addCallback(process)
        return d

    def _get_commit_files(self, rev):
        args = ['log', '-r', rev, '--template={files}']
        d = utils.getProcessOutput(self.hgbin, args, path=self.workdir, env=os.environ, errortoo=False )
        def process(output):
            return output.split()
        d.addCallback(process)
        return d

    def _get_commit_author(self, rev):
        args = ['log', '-r', rev, '--template={author}']
        d = utils.getProcessOutput(self.hgbin, args, path=self.workdir, env=os.environ, errortoo=False )
        def process(output):
            stripped_output = output.strip().decode(self.encoding)
            if not stripped_output:
                raise EnvironmentError('could not get commit author for rev')
            return stripped_output
        d.addCallback(process)
        return d

    def _get_changes(self):
        log.msg('hgpoller: polling hg repo at %s' % self.repourl)

        self.lastPoll = time.time()

        # get a deferred object that performs the fetch
        args = ['pull', '-b', self.branch, self.repourl]

        # This command always produces data on stderr, but we actually do not care
        # about the stderr or stdout from this command. We set errortoo=True to
        # avoid an errback from the deferred. The callback which will be added to this
        # deferred will not use the response.
        d = utils.getProcessOutput(self.hgbin, args,
                    path=self.workdir,
                    env=os.environ, errortoo=True )

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

        # GR: don't know buildbot enivronment too well, but everything seems to
        # indicate that there's no concurrency on pollers.
        # maybe this should be deferred, too ?
        current_filename = os.path.join(self.workdir, 'hgpoller-current')
        try:
            current_file = open(current_filename, 'r')
        except IOError:
            # TODO make a special case for non-writeable etc.
            raise

        current_str = current_file.read().strip()
        current_file.close()
        if current_str:
            # hg log ranges are inclusive
            current = int(current_str)
            revrange = '%d:tip' % (current + 1)
        else:
            # in first iteration, just take the tip of branch
            current = None
            revrange = '%s:tip' % self.branch

        # hg log on a range of revisions is never empty
        # also, if a numeric revision does not exist, a node may match
        # therefore we have to check explicitely that tip > current
        tiprev = yield utils.getProcessOutput(self.hgbin,
                    ['log', '-r', 'tip', '--template={rev}'],
                    path=self.workdir, env=os.environ, errortoo=False )

        if int(tiprev.strip()) <= current:
            return

        # get the change list
        revListArgs = ['log', '-b', self.branch, '-r', revrange,
                       r'--template={rev}:{node}\n']
        self.changeCount = 0
        results = yield utils.getProcessOutput(self.hgbin, revListArgs,
                    path=self.workdir, env=os.environ, errortoo=False )

        revNodeList = [rn.split(':', 1) for rn in results.strip().split()]

        self.changeCount = len(revNodeList)

        log.msg('hgpoller: processing %d changes: %r in %r'
                % (self.changeCount, revNodeList, self.workdir) )

        for rev, node in revNodeList:
            dl = defer.DeferredList([
                self._get_commit_timestamp(rev),
                self._get_commit_author(rev),
                self._get_commit_files(rev),
                self._get_commit_comments(rev),
            ], consumeErrors=True)

            results = yield dl

            # check for failures
            failures = [ r[1] for r in results if not r[0] ]
            if failures:
                # just fail on the first error; they're probably all related!
                current_file.close()
                raise failures[0]

            timestamp, author, files, comments = [ r[1] for r in results ]

            # writing at once in case something goes wrong in later revs
            current_file = open(current_filename, 'w')
            current_file.write(rev + os.linesep) # newline is human nicety
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
