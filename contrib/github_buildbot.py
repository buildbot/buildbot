#!/usr/bin/env python

# This code is largely based on the code from contrib/git_buildbot.py 
#
# To run this program just call `./github_buildbot.py` or run  
# `./github_buildbot.py &` to run in the background.  
#
# Be sure to modify the settings as necessary. You may use
# this service hook for as many github projects as you desire. Just set the 
# post-receive service hook in github to the publically accessible address of
# the server this script runs on.  The default port is 4000.  Example service 
# hook: http://yourserver.com:4000.
#
# github_buildbot.py will determine the repository information from the JSON 
# HTTP POST it receives from github.com and build the appropriate repository.
# If your github repository is private, you must add a ssh key to the github
# repository for the user who initiated github_buildbot.py
#

import tempfile, logging, re, os, sys, commands, subprocess
from twisted.web import server, resource
from twisted.internet import reactor
from twisted.spread import pb
from twisted.cred import credentials
from twisted.internet import reactor
from buildbot.scripts import runner

try:
	import json
except ImportError:
	import simplejson as json

# The port to run the listening HTTP server for github post-receieve hook on

port = 4000

# Modify this for github repo domain (in case you are using something in your
# .ssh/config)

github = 'github.com'

# Modify this to fit your setup, or pass in --master server:host on the
# command line

master = "localhost:9989"

changes = []

class GitHubBuildBot(resource.Resource):
	
	isLeaf = True
	def render_POST(self, request):
		self.payload = json.loads(request.args['payload'][0])
		try:
			self.process_change()
		except:
			raise()
	
	def process_change(self):
		update_git_dir(self.payload['repository']['owner']['name'] , self.payload['repository']['name'])
		[oldrev, newrev, refname] = self.payload['before'], self.payload['after'], self.payload['ref']
		
		# We only care about regular heads, i.e. branches
		m = re.match(r"^refs\/heads\/(.+)$", refname)
		if not m:
			logging.info("Ignoring refname `%s': Not a branch" % refname)

		branch = m.group(1)
		# Find out if the branch was created, deleted or updated. Branches
		# being deleted aren't really interesting.
		if re.match(r"^0*$", newrev):
			logging.info("Branch `%s' deleted, ignoring" % branch)
		elif re.match(r"^0*$", oldrev):
			gen_create_branch_changes(newrev, refname, branch)
		else:
			gen_update_branch_changes(oldrev, newrev, refname, branch)

		# Submit the changes, if any
		if not changes:
			logging.warning("No changes found")
			return
				    
		host, port = master.split(':')
		port = int(port)

		f = pb.PBClientFactory()
		d = f.login(credentials.UsernamePassword("change", "changepw"))
		reactor.connectTCP(host, port, f)

		d.addErrback(connectFailed)
		d.addCallback(connected)


def connectFailed(error):
    logging.error("Could not connect to %s: %s"
            % (master, error.getErrorMessage()))
    return error


def addChange(dummy, remote, changei):
    logging.debug("addChange %s, %s" % (repr(remote), repr(changei)))
    try:
        c = changei.next()
    except StopIteration:
        remote.broker.transport.loseConnection()
        return None
    
    logging.info("New revision: %s" % c['revision'][:8])
    for key, value in c.iteritems():
        logging.debug("  %s: %s" % (key, value))
    
    d = remote.callRemote('addChange', c)
    d.addCallback(addChange, remote, changei)
    return d


def connected(remote):
    return addChange(None, remote, changes.__iter__())


def grab_commit_info(c, rev):
    # Extract information about committer and files using git show
    f = os.popen("git show --raw --pretty=full %s" % rev, 'r')
    
    files = []
    
    while True:
        line = f.readline()
        if not line:
            break
        
        m = re.match(r"^:.*[MAD]\s+(.+)$", line)
        if m:
            logging.debug("Got file: %s" % m.group(1))
            files.append(m.group(1))
            continue
        
        m = re.match(r"^Author:\s+(.+)$", line)
        if m:
            logging.debug("Got author: %s" % m.group(1))
            c['who'] = m.group(1)
        
        if re.match(r"^Merge: .*$", line):
            files.append('merge')
    
    c['files'] = files
    status = f.close()
    if status:
        logging.warning("git show exited with status %d" % status)


def gen_changes(input, branch):
    while True:
        line = input.readline()
        if not line:
            break
        
        logging.debug("Change: %s" % line)
        
        m = re.match(r"^([0-9a-f]+) (.*)$", line.strip())
        c = {'revision': m.group(1),
             'comments': m.group(2),
             'branch': branch,
        }
        grab_commit_info(c, m.group(1))
        changes.append(c)


def gen_create_branch_changes(newrev, refname, branch):
    # A new branch has been created. Generate changes for everything
    # up to `newrev' which does not exist in any branch but `refname'.
    #
    # Note that this may be inaccurate if two new branches are created
    # at the same time, pointing to the same commit, or if there are
    # commits that only exists in a common subset of the new branches.
    
    logging.info("Branch `%s' created" % branch)
    
    f = os.popen("git rev-parse --not --branches"
            + "| grep -v $(git rev-parse %s)" % refname
            + "| git rev-list --reverse --pretty=oneline --stdin %s" % newrev,
            'r')
    
    gen_changes(f, branch)
    
    status = f.close()
    if status:
        logging.warning("git rev-list exited with status %d" % status)


def gen_update_branch_changes(oldrev, newrev, refname, branch):
    # A branch has been updated. If it was a fast-forward update,
    # generate Change events for everything between oldrev and newrev.
    #
    # In case of a forced update, first generate a "fake" Change event
    # rewinding the branch to the common ancestor of oldrev and
    # newrev. Then, generate Change events for each commit between the
    # common ancestor and newrev.
    
    logging.info("Branch `%s' updated %s .. %s"
            % (branch, oldrev[:8], newrev[:8]))
    
    baserev = commands.getoutput("git merge-base %s %s" % (oldrev, newrev))
    logging.debug("oldrev=%s newrev=%s baserev=%s" % (oldrev, newrev, baserev))
    if baserev != oldrev:
        c = {'revision': baserev,
             'comments': "Rewind branch",
             'branch': branch,
             'who': "dummy",
        }
        logging.info("Branch %s was rewound to %s" % (branch, baserev[:8]))
        files = []
        f = os.popen("git diff --raw %s..%s" % (oldrev, baserev), 'r')
        while True:
            line = f.readline()
            if not line:
                break
            
            file = re.match(r"^:.*[MAD]\s*(.+)$", line).group(1)
            logging.debug("  Rewound file: %s" % file)
            files.append(file)
        
        status = f.close()
        if status:
            logging.warning("git diff exited with status %d" % status)
        
        if files:
            c['files'] = files
            changes.append(c)
    
    if newrev != baserev:
        # Not a pure rewind
        f = os.popen("git rev-list --reverse --pretty=oneline %s..%s"
                % (baserev, newrev), 'r')
        gen_changes(f, branch)
        
        status = f.close()
        if status:
            logging.warning("git rev-list exited with status %d" % status)

def update_git_dir(user, repo):
	tempdir = tempfile.gettempdir()
	repodir = tempdir+"/"+repo
	if os.path.exists(repodir):
		os.chdir(repodir)
		subprocess.call(['git','pull'])
	else:
		os.chdir(tempdir)
		subprocess.call(['git','clone', 'git@'+ github+':'+user+'/'+repo+'.git'])
		os.chdir(repodir)

if __name__ == '__main__':
	site = server.Site(GitHubBuildBot())
	reactor.listenTCP(port, site)
	reactor.run()
