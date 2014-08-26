#!/usr/bin/env python

# This script expects one line for each new revision on the form
#   <oldrev> <newrev> <refname>
#
# For example:
#   aa453216d1b3e49e7f6f98441fa56946ddcd6a20
#   68f7abf4e6f922807889f52bc043ecd31b79f814 refs/heads/master
#
# Each of these changes will be passed to the buildbot server along
# with any other change information we manage to extract from the
# repository.
#
# This script is meant to be run from hooks/post-receive in the git
# repository. It can also be run at client side with hooks/post-merge
# after using this wrapper:

# !/bin/sh
# PRE=$(git rev-parse 'HEAD@{1}')
# POST=$(git rev-parse HEAD)
# SYMNAME=$(git rev-parse --symbolic-full-name HEAD)
# echo "$PRE $POST $SYMNAME" | git_buildbot.py
#
# Largely based on contrib/hooks/post-receive-email from git.

import commands
import logging
import os
import re
import sys

from twisted.cred import credentials
from twisted.internet import defer
from twisted.internet import reactor
from twisted.spread import pb

from optparse import OptionParser

# Modify this to fit your setup, or pass in --master server:port on the
# command line

master = "localhost:9989"

# When sending the notification, send this category if (and only if)
# it's set (via --category)

category = None

# When sending the notification, send this repository if (and only if)
# it's set (via --repository)

repository = None

# When sending the notification, send this project if (and only if)
# it's set (via --project)

project = None

# When sending the notification, send this codebase.  If this is None, no
# codebase will be sent.  This can also be set via --codebase

codebase = None

# Username portion of PB login credentials to send the changes to the master
username = "change"

# Password portion of PB login credentials to send the changes to the master
auth = "changepw"

# When converting strings to unicode, assume this encoding.
# (set with --encoding)

encoding = 'utf8'

# If true, takes only the first parent commits. This controls if we want to
# trigger builds for merged in commits (when False).

first_parent = False

# The GIT_DIR environment variable must have been set up so that any
# git commands that are executed will operate on the repository we're
# installed in.

changes = []


def connectFailed(error):
    logging.error("Could not connect to %s: %s", master, error.getErrorMessage())
    return error


def addChanges(remote, changei, src='git'):
    logging.debug("addChanges %s, %s", repr(remote), repr(changei))

    def addChange(c):
        logging.info("New revision: %s", c['revision'][:8])
        for key, value in c.iteritems():
            logging.debug("  %s: %s", key, value)

        c['src'] = src
        d = remote.callRemote('addChange', c)
        return d

    finished_d = defer.Deferred()

    def iter():
        try:
            c = changei.next()
            d = addChange(c)
            # handle successful completion by re-iterating, but not immediately
            # as that will blow out the Python stack

            def cb(_):
                reactor.callLater(0, iter)
            d.addCallback(cb)
            # and pass errors along to the outer deferred
            d.addErrback(finished_d.errback)
        except StopIteration:
            remote.broker.transport.loseConnection()
            finished_d.callback(None)

    iter()
    return finished_d


def connected(remote):
    return addChanges(remote, changes.__iter__())


def grab_commit_info(c, rev):
    # Extract information about committer and files using git show
    f = os.popen("git show --raw --pretty=full %s" % rev, 'r')

    files = []
    comments = []

    while True:
        line = f.readline()
        if not line:
            break

        if line.startswith(4 * ' '):
            comments.append(line[4:])

        m = re.match(r"^:.*[MAD]\s+(.+)$", line)
        if m:
            logging.debug("Got file: %s", m.group(1))
            files.append(unicode(m.group(1), encoding=encoding))
            continue

        m = re.match(r"^Author:\s+(.+)$", line)
        if m:
            logging.debug("Got author: %s", m.group(1))
            c['who'] = unicode(m.group(1), encoding=encoding)

        if re.match(r"^Merge: .*$", line):
            files.append('merge')

    c['comments'] = ''.join(comments)
    c['files'] = files
    status = f.close()
    if status:
        logging.warning("git show exited with status %d", status)


def gen_changes(input, branch):
    while True:
        line = input.readline()
        if not line:
            break

        logging.debug("Change: %s", line)

        m = re.match(r"^([0-9a-f]+) (.*)$", line.strip())
        c = {'revision': m.group(1),
             'branch': unicode(branch, encoding=encoding),
             }

        if category:
            c['category'] = unicode(category, encoding=encoding)

        if repository:
            c['repository'] = unicode(repository, encoding=encoding)

        if project:
            c['project'] = unicode(project, encoding=encoding)

        if codebase:
            c['codebase'] = unicode(codebase, encoding=encoding)

        grab_commit_info(c, m.group(1))
        changes.append(c)


def gen_create_branch_changes(newrev, refname, branch):
    # A new branch has been created. Generate changes for everything
    # up to `newrev' which does not exist in any branch but `refname'.
    #
    # Note that this may be inaccurate if two new branches are created
    # at the same time, pointing to the same commit, or if there are
    # commits that only exists in a common subset of the new branches.

    logging.info("Branch `%s' created", branch)

    f = os.popen("git rev-parse --not --branches"
                 + "| grep -v $(git rev-parse %s)" % refname
                 + "| git rev-list --reverse --pretty=oneline --stdin %s" % newrev,
                 'r')

    gen_changes(f, branch)

    status = f.close()
    if status:
        logging.warning("git rev-list exited with status %d", status)


def gen_create_tag_changes(newrev, refname, tag):
    # A new tag has been created. Generate one change for the commit
    # a tag may or may not coincide with the head of a branch, so
    # the "branch" attribute will hold the tag name.

    logging.info("Tag `%s' created" % tag)
    f = os.popen("git log -n 1 --pretty=oneline %s" % newrev, 'r')
    gen_changes(f, tag)
    status = f.close()
    if status:
        logging.warning("git log exited with status %d", status)


def gen_update_branch_changes(oldrev, newrev, refname, branch):
    # A branch has been updated. If it was a fast-forward update,
    # generate Change events for everything between oldrev and newrev.
    #
    # In case of a forced update, first generate a "fake" Change event
    # rewinding the branch to the common ancestor of oldrev and
    # newrev. Then, generate Change events for each commit between the
    # common ancestor and newrev.

    logging.info("Branch `%s' updated %s .. %s", branch, oldrev[:8], newrev[:8])

    baserev = commands.getoutput("git merge-base %s %s" % (oldrev, newrev))
    logging.debug("oldrev=%s newrev=%s baserev=%s", oldrev, newrev, baserev)
    if baserev != oldrev:
        c = {'revision': baserev,
             'comments': "Rewind branch",
             'branch': unicode(branch, encoding=encoding),
             'who': "dummy",
             }
        logging.info("Branch %s was rewound to %s", branch, baserev[:8])
        files = []
        f = os.popen("git diff --raw %s..%s" % (oldrev, baserev), 'r')
        while True:
            line = f.readline()
            if not line:
                break

            file = re.match(r"^:.*[MAD]\s+(.+)$", line).group(1)
            logging.debug("  Rewound file: %s", file)
            files.append(unicode(file, encoding=encoding))

        status = f.close()
        if status:
            logging.warning("git diff exited with status %d", status)

        if category:
            c['category'] = unicode(category, encoding=encoding)

        if repository:
            c['repository'] = unicode(repository, encoding=encoding)

        if project:
            c['project'] = unicode(project, encoding=encoding)

        if codebase:
            c['codebase'] = unicode(codebase, encoding=encoding)

        if files:
            c['files'] = files
            changes.append(c)

    if newrev != baserev:
        # Not a pure rewind
        options = "--reverse --pretty=oneline"
        if first_parent:
            # Add the --first-parent to avoid adding the merge commits which
            # have already been tested.
            options += ' --first-parent'
        f = os.popen("git rev-list %s %s..%s" % (options, baserev, newrev), 'r')
        gen_changes(f, branch)

        status = f.close()
        if status:
            logging.warning("git rev-list exited with status %d", status)


def cleanup(res):
    reactor.stop()


def process_branch_change(oldrev, newrev, refname, branch):
     # Find out if the branch was created, deleted or updated.
     if re.match(r"^0*$", newrev):
         logging.info("Branch `%s' deleted, ignoring", branch)
     elif re.match(r"^0*$", oldrev):
         gen_create_branch_changes(newrev, refname, branch)
     else:
         gen_update_branch_changes(oldrev, newrev, refname, branch)


def process_tag_change(oldrev, newrev, refname, tag):
    #Process a new tag, or ignore a deleted tag
    if re.match(r"^0*$", newrev):
        logging.info("Tag `%s' deleted, ignoring" % tag)
    elif re.match(r"^0*$", oldrev):
        gen_create_tag_changes(newrev, refname, tag)


def process_change(oldrev, newrev, refname):
    # Identify the change as a branch, tag or other, and process it
    m = re.match(r"^refs\/(heads|tags)\/(.+)$", refname)
    if not m:
        logging.info("Ignoring refname `%s': Not a branch or tag" % refname)
        return

    if m.group(1) == 'heads':
        branch = m.group(2)
        process_branch_change(oldrev, newrev, refname, branch)
    elif m.group(1) == 'tags':
        tag = m.group(2)
        process_tag_change(oldrev, newrev, refname, tag)

def process_changes():
    # Read branch updates from stdin and generate Change events
    while True:
        line = sys.stdin.readline()
        if not line:
            break

        [oldrev, newrev, refname] = line.split(None, 2)
        process_change(oldrev, newrev, refname)


def send_changes():
    # Submit the changes, if any
    if not changes:
        logging.warning("No changes found")
        return

    host, port = master.split(':')
    port = int(port)

    f = pb.PBClientFactory()
    d = f.login(credentials.UsernamePassword(username, auth))
    reactor.connectTCP(host, port, f)

    d.addErrback(connectFailed)
    d.addCallback(connected)
    d.addBoth(cleanup)

    reactor.run()


def parse_options():
    parser = OptionParser()
    parser.add_option("-l", "--logfile", action="store", type="string",
                      help="Log to the specified file")
    parser.add_option("-v", "--verbose", action="count",
                      help="Be more verbose. Ignored if -l is not specified.")
    master_help = ("Build master to push to. Default is %(master)s" %
                   {'master': master})
    parser.add_option("-m", "--master", action="store", type="string",
                      help=master_help)
    parser.add_option("-c", "--category", action="store",
                      type="string", help="Scheduler category to notify.")
    parser.add_option("-r", "--repository", action="store",
                      type="string", help="Git repository URL to send.")
    parser.add_option("-p", "--project", action="store",
                      type="string", help="Project to send.")
    parser.add_option("--codebase", action="store",
                      type="string", help="Codebase to send.")
    encoding_help = ("Encoding to use when converting strings to "
                     "unicode. Default is %(encoding)s." %
                     {"encoding": encoding})
    parser.add_option("-e", "--encoding", action="store", type="string",
                      help=encoding_help)
    username_help = ("Username used in PB connection auth, defaults to "
                     "%(username)s." % {"username": username})
    parser.add_option("-u", "--username", action="store", type="string",
                      help=username_help)
    auth_help = ("Password used in PB connection auth, defaults to "
                 "%(auth)s." % {"auth": auth})
    # 'a' instead of 'p' due to collisions with the project short option
    parser.add_option("-a", "--auth", action="store", type="string",
                      help=auth_help)
    first_parent_help = ("If set, don't trigger builds for merged in commits")
    parser.add_option("--first-parent", action="store_true",
                      help=first_parent_help)
    options, args = parser.parse_args()
    return options


# Log errors and critical messages to stderr. Optionally log
# information to a file as well (we'll set that up later.)
stderr = logging.StreamHandler(sys.stderr)
fmt = logging.Formatter("git_buildbot: %(levelname)s: %(message)s")
stderr.setLevel(logging.ERROR)
stderr.setFormatter(fmt)
logging.getLogger().addHandler(stderr)
logging.getLogger().setLevel(logging.DEBUG)

try:
    options = parse_options()
    level = logging.WARNING
    if options.verbose:
        level -= 10 * options.verbose
        if level < 0:
            level = 0

    if options.logfile:
        logfile = logging.FileHandler(options.logfile)
        logfile.setLevel(level)
        fmt = logging.Formatter("%(asctime)s %(levelname)s: %(message)s")
        logfile.setFormatter(fmt)
        logging.getLogger().addHandler(logfile)

    if options.master:
        master = options.master

    if options.category:
        category = options.category

    if options.repository:
        repository = options.repository

    if options.project:
        project = options.project

    if options.codebase:
        codebase = options.codebase

    if options.username:
        username = options.username

    if options.auth:
        auth = options.auth

    if options.encoding:
        encoding = options.encoding

    if options.first_parent:
        first_parent = options.first_parent

    process_changes()
    send_changes()
except SystemExit:
    pass
except:
    logging.exception("Unhandled exception")
    sys.exit(1)
