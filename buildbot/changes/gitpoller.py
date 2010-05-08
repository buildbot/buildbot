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
    
    def __init__(self, repourl, branch='master', workdir=None, pollinterval=10*60, gitbin='git'):
        """
        @type  repourl: string
        @param repourl: the url that describes the remote repository,
                        e.g. git@example.com:foobaz/myrepo.git

        @type  branch: string
        @param branch: the desired branch to fetch, will default to 'master'
        
        @type  workdir: string
        @param workdir: the directory where the poller should keep its local repository.
                        will default to tempdir/gitpoller_work
                        
        @type  pollinterval: int
        @param pollinterval: interval in seconds between polls, default is 10 minutes
        
        @type  gitbin: string
        @param path to the git binary, defaults to just 'git'
        """
        
        self.repourl = repourl
        self.branch = branch
        self.pollinterval = pollinterval
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
            os.system(self.gitbin + ' clone ' + self.repourl + ' ' + self.workdir)
        
        reactor.callLater(0, self.loop.start, self.pollinterval)

    def stopService(self):
        self.loop.stop()
        return base.ChangeSource.stopService(self)

    def describe(self):
        str = 'GitPoller watching the remote git repository %s, branch: %s ' \
                % (self.repourl, self.branch)
        return str

    def poll(self):
        if self.working:
            log.msg('gitpoller: not polling git repo because last poll is still working')
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
                output = p.communicate()[0]
                break
            except (OSError, select.error), e:
                if e[0] == errno.EINTR:
                    continue
                else:
                    raise
        
        if p.returncode != 0:
            raise Exception('call \'%s\' exited with error \'%s\', output: \'%s\'' % 
                            (args, p.returncode, output))
        return output

    def _get_commit_comments(self, rev):
        args = ['log', rev, '--no-walk', r'--format=%s%n%b']
        output = self._get_git_output(args)
        
        if len(output.strip()) == 0:
            raise Exception('could not get commit comment for rev %s' % rev)
        
        return output

    def _get_commit_timestamp(self, rev):
        # unix timestamp
        args = ['log', rev, '--no-walk', r'--format=%ct']
        output = self._get_git_output(args)
        
        try:
            stamp = float(output)
        except Exception, e:
            log.msg('gitpoller: caught exception converting output \'%s\' to timestamp' % output)
            raise e
        
        return stamp
        
    def _get_commit_files(self, rev):
        args = ['log', rev, '--name-only', '--no-walk', r'--format=%n']
        fileList = self._get_git_output(args).split()
        return fileList
            
    def _get_commit_name(self, rev):
        args = ['log', rev, '--no-walk', r'--format=%cn']
        output = self._get_git_output(args)
        
        if len(output.strip()) == 0:
            raise Exception('could not get commit name for rev %s' % rev)

        return output

    def _get_changes(self):
        log.msg('gitpoller: polling git repo at %s' % self.repourl)

        self.lastPoll = time.time()
        os.chdir(self.workdir)
        
        # get a deferred object that performs the fetch
        args = ['fetch', self.repourl, self.branch]
        d = utils.getProcessOutput(self.gitbin, args, env={}, errortoo=1 )

        return d

    def _process_changes(self, res):
        # get the change list
        revListArgs = ['log', 'HEAD..FETCH_HEAD', r'--format=%H']
        revs = self._get_git_output(revListArgs);
        revCount = 0
        
        # process oldest change first
        revList = revs.split()
        if revList:
            revList.reverse()
            revCount = len(revList)
            
        log.msg('gitpoller: processing %d changes' % revCount )

        for rev in revList:
            c = changes.Change(who = self._get_commit_name(rev),
                               files = self._get_commit_files(rev),
                               comments = self._get_commit_comments(rev),
                               when = self._get_commit_timestamp(rev),
                               branch = self.branch)
            self.parent.addChange(c)
            self.lastChange = self.lastPoll
            
    def _catch_up(self, res):
        log.msg('gitpoller: catching up to FETCH_HEAD')
        
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
        