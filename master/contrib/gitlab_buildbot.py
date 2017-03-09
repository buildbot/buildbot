#!/usr/bin/python
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

"""\
gitlab merge request -> buildbot try build integration
======================================================

This file contains a draft implementation of a merge request webhook for
gitlab that triggers a try build on buildbot, and adds a comment to the
merge request on gitlab when the build starts and when it finishes.

------------
Requirements
------------

This has been tested with Buildbot 0.8.8 and Gitlab 7.11.4-ee.

Assumes you have installed the following Python packages:

- pyapi-gitlab (https://github.com/Itxaka/pyapi-gitlab)
- Requests (http://www.python-requests.org/)

If buildbot has been patched with the draft fix for 
http://trac.buildbot.net/ticket/3333, the comments added 
to the gitlab build request page will hyperlink straight to
failed builds.

-------------
Configuration
-------------

Assumes that you've set up buildbot to accept PB style try builds,
and that 'buildbot try -c pb --username=XXXXX --passwd=YYYYY ...' already works.
e.g. master.cfg should contain something like
   self['schedulers'].append(
       Try_Userpass(
           port=7890,
           userpass=['XXXXX', 'YYYYY'],
           name="try",
           builderNames=[...your try buildernames...]
       ))
See http://buildbot.readthedocs.org/en/v0.8.8/tutorial/tour.html#adding-a-try-scheduler

In a gitlab project's settings page, click on Web Hooks, uncheck Push Events,
check Merge Request events, and enter hostname:9999 in the URL field, where hostname
is the machine that will run this script.
(Don't click Test Hook, as that sends a push event, not a merge request event.)

In a gitlab user's profile, click on Account, then copy the Private Token
and use it in the next step.  (It will allow this script to post comments to
merge requests.)  Make sure the user has at least guest permissions on the
projects of interest.

Create a file gitlab_buildbot.json in the home directory containing
the info needed to access the buildbot web server, its try server,
the gitlab web server, and a user's private gitlab token.
request.  For instance:

{
   "web_status" : "http://buildhost.fakeexample.com:8080",
   "try_server" : "buildhost.fakeexample.com:7890",
   "try_user"   : "XXXXX",
   "try_pass"   : "YYYYY",
   "gitlaburl"  : "https://gitlab.fakeexample.com",
   "gitlabtoken": "XXXXX"
}

Start this server with e.g.
    python /usr/bin/gitlab_buildbot.py 9999
then create a merge request in gitlab.  Watch this server's stdout
to make sure the merge request is properly received and processed.

---------------
Troubleshooting
---------------

You can run this to submit a single try job as follows:
    python /usr/bin/gitlab_buildbot.py project comment surl sbranch uurl ubranch who project_id mr_id

------------
Known Issues
------------

Uses 'git format-patch', and buildbot uses moral equivalent of 'git
am' to apply the resulting patch.  That should be fine, but alas, git
explodes if the change adds or removes the final newline of the file;
if this bites you, commit a final-whitespace-only change first before
trying to do a try build.

Should authenticate its incoming webhook.

Should sanitize input better.

Should probably be rewritten to use twisted, and merged into
master/buildbot/status/web/hooks/gitlab.py, which already handles
gitlab push notifications.

If this doesn't reply quickly enough to gitlab, gitlab will resend the
hook, which slows things down further, causing another resend, etc.,
etc., ad nauseum.  This shouldn't happen anymore, but if it does, Gitlab
supposedly has a knob to increase the timeout interval, which might help.

-------------------
Contact Information
-------------------

Maintainer/author: dank@kegel.com
"""

import os
import re
import shutil
import simplejson  # for when you want better error messages
import subprocess
import tempfile
import time
import traceback
import sys
import urllib
from sys import version as python_version
from cgi import parse_header, parse_multipart

if python_version.startswith('3'):
    from urllib.parse import parse_qs
    from http.server import BaseHTTPRequestHandler, HTTPServer
    from socketserver import ForkingMixIn
else:
    from urlparse import parse_qs
    from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
    from SocketServer import ForkingMixIn

# On Ubuntu 12.04, you can install Requests via apt-get install python-requests,
# but you'll need to modify pyapi-gitlab slightly to run against that old version.
# Allow using a non-installed package pyapi-gitlab in a subdirectory
# (in my case, I copied just its gitlab subdirectory here, then edited it
# slightly to not pass the verify parameters that old Requests doesn't support).
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + '/gitlab')

import gitlab

class ForkingHTTPServer(ForkingMixIn, HTTPServer):
    """Handle requests in a separate process."""

def my_quote(s):
    return urllib.quote(s).replace("%20", " ")

def verbose_system(s):
    print(s)
    sys.stdout.flush()
    try:
        subprocess.check_call('( '+ s + ') > log.txt 2>&1', shell=True)
    except:
        print("Failed!  Log:")
        os.system("cat log.txt")
        raise

def do_try(project, comment, surl, sbranch, uurl, ubranch, who, project_id, mr_id):
    print("do_try start: project is " + project)
    print("comment is " + comment)
    sys.stdout.flush()
    secrets = simplejson.load(open(os.path.expanduser("~/gitlab_buildbot.json")))
    try_server = secrets["try_server"]
    try_user = secrets["try_user"]
    try_pass = secrets["try_pass"]
    web_status = secrets["web_status"]
    gitlaburl = secrets["gitlaburl"]
    gitlabtoken = secrets["gitlabtoken"]

    builders_str = subprocess.check_output("time buildbot try -c pb --username=%s --passwd=%s -m %s --get-builder-names | grep -w '%s.*%s'" % (try_user, try_pass, try_server, project, ubranch), shell=True)

    opts=" ".join(["-b " + x for x in builders_str.split()])
    dirpath = tempfile.mkdtemp()
    verbose_system("time git clone -b %s %s %s" % (ubranch, uurl, dirpath))
    verbose_system("cd %s && time git remote add downstream %s && git fetch downstream" % (dirpath, surl))
    verbose_system("cd %s && time git checkout -b branch-to-try--%s downstream/%s" % (dirpath, sbranch, sbranch))
    verbose_system("cd %s && time git format-patch -M -B origin/%s --stdout > change.patch" % (dirpath, ubranch))

    git = gitlab.Gitlab(gitlaburl, token=gitlabtoken)

    cmd = "buildbot try --wait -c pb --username=%s --who='%s' --passwd=%s -m %s --diff=change.patch --patchlevel 1 %s --comment '%s'" % (try_user, my_quote(who), try_pass, try_server, opts, my_quote(comment))

    msg = "Running try build, command: %s" % cmd
    msg = re.sub('--passwd=[^ ]*', '--passwd=nottellingyou', msg)
    print(msg)
    sys.stdout.flush()

    git.addcommenttomergerequest(project_id, mr_id, msg)

    # truncate log
    f = open("log.txt", "w")
    cmd = "cd %s && %s" % (dirpath, cmd)
    try:
        # FIXME: "buildbot try" outputs status every 30 seconds, maybe we should
        # loop reading it and submitting comments while waiting for it to finish.
        subprocess.check_call('( '+ cmd + ') > log.txt 2>&1', shell=True)
        result = "PASS"
    except:
        result = "FAIL"
    f = open("log.txt", "r")
    log = f.read()
    # Remove non-interesting lines. (?s) means 'dot matches newline too'.  Comment this out while debugging.
    log = re.sub(r'(?s).*All Builds Complete', '', log)
    msg = "Try build result: %s\n%s" % (result, log)
    # Basic HTML formatting
    # Add line breaks.
    htmlmsg = msg.replace("\n", "<br>\n")
    # Turn build numbers into hyperlinks.
    htmlmsg = re.sub(r'(\S*): (.*\[)build (\d+)', r'\1: \2<a href="%s/builders/\1/builds/\3">build \3</a>' % web_status, htmlmsg)
    # Turn builder names into hyperlinks.
    htmlmsg = re.sub(r'(\S*): (shell|failure)', r'<a href="%s/builders/\1">\1</a>: \2' % web_status, htmlmsg)

    git.addcommenttomergerequest(project_id, mr_id, htmlmsg)

    shutil.rmtree(dirpath)
    print(msg)
    sys.stdout.flush()

def do_merge_request(postvars):
 
    print("Time: " + time.strftime("%c"))
    print("object_kind is " + postvars['object_kind'])
    o = postvars['object_attributes']
    project_id = o['target_project_id']
    print("project_id is %s" % project_id)
    mr_id = o['id']
    print("mr_id is %s" % mr_id)
    print("author is " + o['last_commit']['author']['name'])
    print("email is " + o['last_commit']['author']['email'])
    print("title is " + o['title'])
    print("description is " + o['description'])
    print("state is " + o['state'])
    print("merge_status is " + o['merge_status'])
    if o['state'] == 'closed' or o['merge_status'] != 'unchecked':
        print("skipping to avoid multiple runs on same merge request")
        sys.stdout.flush()
        return
    sys.stdout.flush()
    do_try(project = o['target']['name'], surl = o['source']['ssh_url'],
           sbranch = o['source_branch'], uurl = o['target']['ssh_url'],
           ubranch = o['target_branch'], comment=o['title'],
           who=o['last_commit']['author']['email'], project_id=project_id,
           mr_id=mr_id)

class RequestHandler(BaseHTTPRequestHandler):

    def reply_fail(self, val=400, reason='unknown'):
	message = 'Error: ' + reason
        self.send_response(val)
        self.send_header('Content-type', 'text')
	self.send_header("Content-length", str(len(message)))
        self.end_headers()
	self.wfile.write(message)
        self.wfile.close()

    def reply_ok(self):
	message = 'OK'
        self.send_response(200)
        self.send_header('Content-type', 'text')
	self.send_header("Content-length", str(len(message)))
        self.end_headers()
	self.wfile.write(message)
        self.wfile.close()
 
    def parse_POST(self):
        ctype, pdict = parse_header(self.headers['content-type'])
        if ctype == 'application/json':
            length = int(self.headers['content-length'])
            post = self.rfile.read(length)
            print("Got " + post)
            postvars = simplejson.loads(post)
        else:
            postvars = {}
        return postvars

    def do_POST(self):
        postvars = self.parse_POST()
        if postvars == {} or 'object_kind' not in postvars:
            self.reply_fail(400, reason='parse error')
        elif postvars['object_kind'] == "merge_request":
            try:
                # Have to reply immediately or gitlab will resend
                self.reply_ok()
                do_merge_request(postvars)
            except:
                traceback.print_exc()
        else:
            self.reply_fail(400, reason='cannot handle object_kind=%s' % postvars['object_kind'])

def run(server_class=ForkingHTTPServer, handler_class=RequestHandler, port=80):
    server_address = ('', port)
    httpd = server_class(server_address, handler_class)
    print 'Starting httpd...'
    sys.stdout.flush()
    httpd.serve_forever()
 
if __name__ == "__main__":
    from sys import argv
 
    if len(argv) == 10:
        # for debugging only
        #      project, comment, surl,    sbranch, uurl,    ubranch, who,     project_id, mr_id
        do_try(argv[1], argv[2], argv[3], argv[4], argv[5], argv[6], argv[7], argv[8], argv[9])
    elif len(argv) == 2:
        run(port=int(argv[1]))
    else:
        run()
