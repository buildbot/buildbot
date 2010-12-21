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

from buildbot.changes import base, changes

class GitPoller(base.PollingChangeSource):
    """This source will poll a remote git repo for changes and submit
    them to the change master."""
    
    compare_attrs = ["repourl", "branch", "workdir",
                     "pollInterval", "gitbin", "usetimestamps",
                     "category", "project"]
                     
    def __init__(self, repourl, branch='master', 
                 workdir=None, pollInterval=10*60, 
                 gitbin='git', usetimestamps=True,
                 category=None, project=None,
                 pollinterval=-2):
        # for backward compatibility; the parameter used to be spelled with 'i'
        if pollinterval != -2:
            pollInterval = pollinterval
        if project is None: project = ''

        self.repourl = repourl
        self.branch = branch
        self.pollInterval = pollInterval
        self.lastChange = time.time()
        self.lastPoll = time.time()
        self.gitbin = gitbin
        self.workdir = workdir
        self.usetimestamps = usetimestamps
        self.category = category
        self.project = project
        self.changeCount = 0
        self.commitInfo  = {}
        
        if self.workdir == None:
            self.workdir = tempfile.gettempdir() + '/gitpoller_work'

    def startService(self):
        base.PollingChangeSource.startService(self)
        
        if not os.path.exists(self.workdir):
            log.msg('gitpoller: creating working dir %s' % self.workdir)
            os.makedirs(self.workdir)
            
        if not os.path.exists(self.workdir + r'/.git'):
            log.msg('gitpoller: initializing working dir')
            os.system(self.gitbin + ' clone --no-checkout ' + self.repourl + ' ' + self.workdir)
            os.system('cd ' + self.workdir + ' && ' + self.gitbin + ' checkout ' + self.branch)
        
    def describe(self):
        status = ""
        if not self.parent:
            status = "[STOPPED - check log]"
        str = 'GitPoller watching the remote git repository %s, branch: %s %s' \
                % (self.repourl, self.branch, status)
        return str

    def poll(self):
        d = self._get_changes()
        d.addCallback(self._process_changes)
        d.addErrback(self._process_changes_failure)
        d.addCallback(self._catch_up)
        d.addErrback(self._catch_up_failure)
        return d

    def _get_commit_comments(self, rev):
        args = ['log', rev, '--no-walk', r'--format=%s%n%b']
        d = utils.getProcessOutput(self.gitbin, args, path=self.workdir, env={}, errortoo=False )
        d.addCallback(self._get_commit_comments_from_output)
        return d

    def _get_commit_comments_from_output(self,git_output):
        stripped_output = git_output.strip()
        if len(stripped_output) == 0:
            raise EnvironmentError('could not get commit comment for rev')
        self.commitInfo['comments'] = stripped_output
        return self.commitInfo['comments'] # for tests

    def _get_commit_timestamp(self, rev):
        # unix timestamp
        args = ['log', rev, '--no-walk', r'--format=%ct']
        d = utils.getProcessOutput(self.gitbin, args, path=self.workdir, env={}, errortoo=False )
        d.addCallback(self._get_commit_timestamp_from_output)
        return d

    def _get_commit_timestamp_from_output(self, git_output):
        stripped_output = git_output.strip()
        if self.usetimestamps:
            try:
                stamp = float(stripped_output)
            except Exception, e:
                    log.msg('gitpoller: caught exception converting output \'%s\' to timestamp' % stripped_output)
                    raise e
            self.commitInfo['timestamp'] = stamp
        else:
            self.commitInfo['timestamp'] = None
        return self.commitInfo['timestamp'] # for tests

    def _get_commit_files(self, rev):
        args = ['log', rev, '--name-only', '--no-walk', r'--format=%n']
        d = utils.getProcessOutput(self.gitbin, args, path=self.workdir, env={}, errortoo=False )
        d.addCallback(self._get_commit_files_from_output)
        return d

    def _get_commit_files_from_output(self, git_output):
        fileList = git_output.split()
        self.commitInfo['files'] = fileList
        return self.commitInfo['files'] # for tests
            
    def _get_commit_name(self, rev):
        args = ['log', rev, '--no-walk', r'--format=%aE']
        d = utils.getProcessOutput(self.gitbin, args, path=self.workdir, env={}, errortoo=False )
        d.addCallback(self._get_commit_name_from_output)
        return d

    def _get_commit_name_from_output(self, git_output):
        stripped_output = git_output.strip()
        if len(stripped_output) == 0:
            raise EnvironmentError('could not get commit name for rev')
        self.commitInfo['name'] = stripped_output
        return self.commitInfo['name'] # for tests

    def _get_changes(self):
        log.msg('gitpoller: polling git repo at %s' % self.repourl)

        self.lastPoll = time.time()
        
        # get a deferred object that performs the fetch
        args = ['fetch', self.repourl, self.branch]
        # This command always produces data on stderr, but we actually do not care
        # about the stderr or stdout from this command. We set errortoo=True to
        # avoid an errback from the deferred. The callback which will be added to this
        # deferred will not use the response.
        d = utils.getProcessOutput(self.gitbin, args, path=self.workdir, env={}, errortoo=True )

        return d

    def _process_changes(self, unused_output):
        # get the change list
        revListArgs = ['log', 'HEAD..FETCH_HEAD', r'--format=%H']
        d = utils.getProcessOutput(self.gitbin, revListArgs, path=self.workdir, env={}, errortoo=False )
        d.addCallback(self._process_changes_in_output)
        return d
    
    def _process_changes_in_output(self, git_output):
        self.changeCount = 0
        
        # process oldest change first
        revList = git_output.split()
        if revList:
            revList.reverse()
            self.changeCount = len(revList)
            
        log.msg('gitpoller: processing %d changes: %s in "%s"' % (self.changeCount, revList, self.workdir) )

        for rev in revList:
            self.commitInfo = {}

            deferreds = [
                                self._get_commit_timestamp(rev),
                                self._get_commit_name(rev),
                                self._get_commit_files(rev),
                                self._get_commit_comments(rev),
                        ]
            dl = defer.DeferredList(deferreds)
            dl.addCallback(self._add_change,rev)        


    def _add_change(self, results, rev):
        log.msg('gitpoller: _add_change results: "%s", rev: "%s" in "%s"' % (results, rev, self.workdir))

        c = changes.Change(who=self.commitInfo['name'],
                               revision=rev,
                               files=self.commitInfo['files'],
                               comments=self.commitInfo['comments'],
                               when=self.commitInfo['timestamp'],
                               branch=self.branch,
                               category=self.category,
                               project=self.project,
                               repository=self.repourl)
        log.msg('gitpoller: change "%s" in "%s"' % (c, self.workdir))
        self.parent.addChange(c)
        self.lastChange = self.lastPoll
            

    def _process_changes_failure(self, f):
        log.msg('gitpoller: repo poll failed')
        log.err(f)
        # eat the failure to continue along the defered chain - we still want to catch up
        return None
        
    def _catch_up(self, res):
        if self.changeCount == 0:
            log.msg('gitpoller: no changes, no catch_up')
            return
        log.msg('gitpoller: catching up to FETCH_HEAD')
        args = ['reset', '--hard', 'FETCH_HEAD']
        d = utils.getProcessOutputAndValue(self.gitbin, args, path=self.workdir, env={})
        def convert_nonzero_to_failure(res):
            (stdout, stderr, code) = res
            if code != 0:
                raise EnvironmentError('catch up failed with exit code: %d' % code)
        d.addCallback(convert_nonzero_to_failure)
        return d

    def _catch_up_failure(self, f):
        log.err(f)
        log.msg('gitpoller: please resolve issues in local repo: %s' % self.workdir)
        # this used to stop the service, but this is (a) unfriendly to tests and (b)
        # likely to leave the error message lost in a sea of other log messages
