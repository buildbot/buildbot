import time
import tempfile
import os
import subprocess

import select
import errno

from twisted.python import log, failure
from twisted.internet import defer, reactor, utils
from twisted.internet.task import LoopingCall
from twisted.web.client import getPage

from buildbot.changes import base, changes

class GitPoller(base.ChangeSource):
    """This source will poll a remote git repo for changes and submit
    them to the change master."""
    
    compare_attrs = ["repourl", "branch", "workdir",
                     "pollinterval", "gitbin", "usetimestamps",
                     "category", "project"]
                     
    parent = None # filled in when we're added
    loop = None
    volatile = ['loop']
    working = False
    running = False
    
    def __init__(self, repourl, branch='master', 
                 workdir=None, pollinterval=10*60, 
                 gitbin='git', usetimestamps=True,
                 category=None, project=None):
        """
        @type  repourl: string
        @param repourl: the url that describes the remote repository,
                        e.g. git@example.com:foobaz/myrepo.git

        @type  branch: string
        @param branch: the desired branch to fetch, will default to 'master'
        
        @type  workdir: string
        @param workdir: the directory where the poller should keep its local repository.
                        will default to <tempdir>/gitpoller_work
                        
        @type  pollinterval: int
        @param pollinterval: interval in seconds between polls, default is 10 minutes
        
        @type  gitbin: string
        @param gitbin: path to the git binary, defaults to just 'git'
        
        @type  usetimestamps: boolean
        @param usetimestamps: parse each revision's commit timestamp (default True), or
                              ignore it in favor of the current time (to appear together
                              in the waterfall page)
                              
        @type  category:     string
        @param category:     catergory associated with the change. Attached to
                             the Change object produced by this changesource such that
                             it can be targeted by change filters.
                             
        @type  project       string
        @param project       project that the changes are associated to. Attached to
                             the Change object produced by this changesource such that
                             it can be targeted by change filters.
        """
        
        self.repourl = repourl
        self.branch = branch
        self.pollinterval = pollinterval
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
        self.loop = LoopingCall(self.poll)
        base.ChangeSource.startService(self)
        
        if not os.path.exists(self.workdir):
            log.msg('gitpoller: creating working dir %s' % self.workdir)
            os.makedirs(self.workdir)
            
        if not os.path.exists(self.workdir + r'/.git'):
            log.msg('gitpoller: initializing working dir')
            os.system(self.gitbin + ' clone ' + self.repourl + ' ' + self.workdir)
        
        reactor.callLater(0, self.loop.start, self.pollinterval)
        
        self.running = True

    def stopService(self):
        if self.running:
            self.loop.stop()
        self.running = False
        return base.ChangeSource.stopService(self)

    def describe(self):
        status = ""
        if not self.running:
            status = "[STOPPED - check log]"
        str = 'GitPoller watching the remote git repository %s, branch: %s %s' \
                % (self.repourl, self.branch, status)
        return str

    def poll(self):
        if self.working:
            log.msg('gitpoller: not polling git repo because last poll is still working')
        else:
            self.working = True
            d = self._get_changes()
            d.addCallback(self._process_changes)
            d.addCallbacks(self._changes_finished_ok, self._changes_finished_failure)
            d.addCallback(self._catch_up)
            d.addCallbacks(self._catch_up_finished_ok, self._catch_up__finished_failure)
        return

    def _get_git_output(self, args):
        git_args = [self.gitbin] + args
        
        p = subprocess.Popen(git_args,
                             cwd=self.workdir,
                             stdout=subprocess.PIPE)
        
        # dirty hack - work around EINTR oddness on Mac builder

        while True:
            try:
                log.msg('gitpoller: about to run "%s" in "%s"' % (git_args, self.workdir))
                output = p.communicate()[0]
                log.msg('gitpoller: finished`run "%s" in "%s"' % (git_args, self.workdir))
                break
            except (OSError, select.error), e:
                error_name = errno.errorcode[e[0]]
                log.msg('gitpoller: caught exception with errno "%s"' % error_name)
                if e[0] == errno.EINTR:
                    continue
                else:
                    raise
        
        if p.returncode != 0:
            raise EnvironmentError('call \'%s\' exited with error \'%s\', output: \'%s\'' % 
                                    (args, p.returncode, output))
        return output

    def _get_commit_comments(self, rev):
        args = ['log', rev, '--no-walk', r'--format=%s%n%b']
        d = utils.getProcessOutput(self.gitbin, args, path=self.workdir, env={}, errortoo=False )
        d.addCallback(self._get_commit_comments_from_output)
        return d

    def _get_commit_comments_from_output(self,git_output):
        stripped_output = git_output.strip()
        log.msg('gitpoller: _get_commit_comments_from_output "%s" for "%s"' % (stripped_output, self.repourl))
        if len(stripped_output) == 0:
            raise EnvironmentError('could not get commit comment for rev %s' % rev)
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
        log.msg('gitpoller: _get_commit_name_from_output "%s" for "%s"' % (stripped_output, self.repourl))
        if len(stripped_output) == 0:
            raise EnvironmentError('could not get commit name for rev %s' % rev)
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
        #log.msg('gitpoller: _process_changes called with ARG "%s"' % res)
        # get the change list
        revListArgs = ['log', 'HEAD..FETCH_HEAD', r'--format=%H']
        d = utils.getProcessOutput(self.gitbin, revListArgs, path=self.workdir, env={}, errortoo=False )
        d.addCallback(self._process_changes_in_output)
        return d
    
    def _process_changes_in_output(self, git_output):
        log.msg('gitpoller: _process_changes_in_output with "%s"' % git_output)
        self.changeCount = 0
        
        # process oldest change first
        revList = git_output.split()
        if revList:
            revList.reverse()
            self.changeCount = len(revList)
            
        log.msg('gitpoller: processing %d changes: "%s" in "%s"' % (self.changeCount, revList, self.workdir) )

        for rev in revList:
            log.msg('gitpoller: _process_changes_in_output "%s" in "%s"' % (rev, self.workdir))
            self.commitInfo = {}

            deferreds = [
                                self._get_commit_timestamp(rev),
                                self._get_commit_name(rev),
                                self._get_commit_files(rev),
                                self._get_commit_comments(rev),
                        ]
            log.msg('gitpoller: _process_changes_in_output deferreds "%s" in "%s"' % (deferreds, self.workdir))
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
            

    def _catch_up(self, res):
        if self.changeCount == 0:
            log.msg('gitpoller: no changes, no catch_up')
            return self.changeCount
        log.msg('gitpoller: catching up to FETCH_HEAD')
        args = ['reset', '--hard', 'FETCH_HEAD']
        d = utils.getProcessOutputAndValue(self.gitbin, args, path=self.workdir, env={})
        return d;

    def _changes_finished_ok(self, res):
        assert self.working
        # check for failure -- this is probably never hit but the twisted docs
        # are not clear enough to be sure. it is being kept "just in case"
        if isinstance(res, failure.Failure):
            return self._changes_finished_failure(res)

        return res

    def _changes_finished_failure(self, res):
        log.msg('gitpoller: repo poll failed: %s' % res)
        assert self.working
        # eat the failure to continue along the defered chain 
        # - we still want to catch up
        return None
        
    def _catch_up_finished_ok(self, res):
        assert self.working

        # check for failure -- this is probably never hit but the twisted docs
        # are not clear enough to be sure. it is being kept "just in case"
        if isinstance(res, failure.Failure):
            return self._catch_up__finished_failure(res)
            
        elif isinstance(res, tuple):
            (stdout, stderr, code) = res
            if code != 0:
                e = EnvironmentError('catch up failed with exit code: %d' % code)
                return self._catch_up__finished_failure(failure.Failure(e))
        
        self.working = False
        return res

    def _catch_up__finished_failure(self, res):
        assert self.working
        assert isinstance(res, failure.Failure)
        self.working = False

        log.msg('gitpoller: catch up failed: %s' % res)
        log.msg('gitpoller: stopping service - please resolve issues in local repo: %s' %
                self.workdir)
        self.stopService()
        return res
        

