import time
import tempfile
import os
import subprocess

import select
import errno

from twisted.python import log, failure
from twisted.internet import reactor, utils
from twisted.internet.task import LoopingCall
from twisted.web.client import getPage

from buildbot.changes import base, changes

class GitPoller(base.ChangeSource):
    """This source will poll a remote git repo for changes and submit
    them to the change master."""

    parent = None # filled in when we're added
    loop = None
    volatile = ['loop']
    working = False
    
    def __init__(self, repoURL, branch='master', workdir=None, pollInterval=30, gitbin='git'):
        """
        @type  repoURL: string
        @param repoURL: the url that describes the remote repository,
                        e.g. git@example.com:foobaz/myrepo.git

        @type  branch: string
        @param branch: the desired branch to fetch, will default to 'master'
        
        @type  workdir: string
        @param workdir: the directory where the poller should keep its local repository.
                        will default to tempdir/gitpoller_work
                        
        @type  pollinterval: int
        @param pollinterval: interval in seconds between polls
        
        @type  gitbin
        @param path to the git binary, defaults to just 'git'
        """
        
        self.repoURL = repoURL
        self.branch = branch
        self.pollInterval = pollInterval
        self.lastChange = time.time()
        self.lastPoll = time.time()
        self.gitbin = gitbin
        self.workdir = workdir;
        
        if self.workdir == None:
            self.workdir = tempfile.gettempdir() + '/gitpoller_work'

    def startService(self):
        self.loop = LoopingCall(self.poll)
        base.ChangeSource.startService(self)
        
        if not os.path.exists(self.workdir):
            log.msg('gitpoller: creating working dir %s' % self.workdir)
            os.makedirs(self.workdir)
            
        if not os.path.exists(self.workdir + r'/.git'):
            log.msg('gitpoller: initializing working dir')
            os.system(self.gitbin + ' clone ' + self.repoURL + ' ' + self.workdir)
        
        reactor.callLater(0, self.loop.start, self.pollInterval)

    def stopService(self):
        self.loop.stop()
        return base.ChangeSource.stopService(self)

    def describe(self):
        str = 'Getting changes from the git remote repository %s, branch: %s ' \
                % (self.repoURL, self.branch)
        return str

    def poll(self):
        if self.working:
            log.msg('gitpoller: Not polling git repo because last poll is still working')
        else:
            self.working = True
            d = self._get_changes()
            d.addCallback(self._process_changes)
            d.addCallback(self._catch_up)
            d.addCallbacks(self._finished_ok, self._finished_failure)
        return

    def _get_git_output(self, args):
        git_args = [self.gitbin] + args
        
        p = subprocess.Popen(git_args,
                             cwd=self.workdir,
                             stdout=subprocess.PIPE)
        
        # dirty hack - work around EINTR oddness on Mac builder
        while True:
            try:
                return p.communicate()[0]
            except (OSError, select.error), e:
                if e[0] == errno.EINTR:
                    continue
                else:
                    raise
                  
    def _get_commit_comments(self, rev):
        args = ['log', rev, '--no-walk', r'--format=%s%n%b']
        return self._get_git_output(args)
        
    def _get_commit_date(self, rev):
        # ISO 8601 time
        args = ['log', rev, '--no-walk', r'--format=%ci']
        return self._get_git_output(args)
        
    def _get_commit_files(self, rev):
        args = ['log', rev, '--name-only', '--no-walk', r'--format=%n']
        return self._get_git_output(args).split()
    
    def _get_commit_name(self, rev):
        args = ['log', rev, '--no-walk', r'--format=%cn']
        return self._get_git_output(args)

    def _get_changes(self):
        log.msg('gitpoller: Polling git repo at %s' % self.repoURL)

        self.lastPoll = time.time()
        os.chdir(self.workdir)
        
        # get a deferred object that performs the fetch
        args = ['fetch', self.repoURL, self.branch]
        d = utils.getProcessOutput(self.gitbin, args, env={}, errortoo=1 )
        
        return d

    def _process_changes(self, res):
        # get the change list
        revListArgs = ['log', 'HEAD..FETCH_HEAD', r'--format=%H']
        revs = self._get_git_output(revListArgs);
        
        # process oldest change first
        revList = revs.split()
        if revList:
            revList.reverse()
        
        log.msg('gitpoller: processing %d changes' % len(revs) )

        for rev in revList:
            c = changes.Change(who = self._get_commit_name(rev),
                               files = self._get_commit_files(rev),
                               comments = self._get_commit_comments(rev),
                               # when = self._get_commit_date(rev),
                               branch = self.branch)
            self.parent.addChange(c)
            self.lastChange = self.lastPoll
            
    def _catch_up(self, res):
        args = ['reset', '--hard', 'FETCH_HEAD']
        d = utils.getProcessOutput(self.gitbin, args, env={}, errortoo=1 )
        return d;

    def _finished_ok(self, res):
        assert self.working
        self.working = False
        
        # check for failure -- this is probably never hit but the twisted docs
        # are not clear enough to be sure. it is being kept "just in case"
        if isinstance(res, failure.Failure):
            log.msg('gitpoller: repo poll failed: %s' % res)
        return res

    def _finished_failure(self, res):
        log.msg('gitpoller: repo poll failed: %s' % res)
        assert self.working
        self.working = False
        return None # eat the failure
        