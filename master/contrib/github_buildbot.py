#!/usr/bin/env python
"""
github_buildbot.py is based on git_buildbot.py. Last revised on 2014-02-20.

github_buildbot.py will determine the repository information from the JSON
HTTP POST it receives from github.com and build the appropriate repository.
If your github repository is private, you must add a ssh key to the github
repository for the user who initiated the build on the buildslave.

This version of github_buildbot.py parses v3 of the github webhook api, with the
"application.vnd.github.v3+json" payload. Configure *only* "push" events to
trigger this webhook.

"""

import hmac
import logging
import os
import sys

from hashlib import sha1
from httplib import ACCEPTED
from httplib import BAD_REQUEST
from httplib import INTERNAL_SERVER_ERROR
from httplib import OK
from optparse import OptionParser

from twisted.cred import credentials
from twisted.internet import reactor
from twisted.spread import pb
from twisted.web import resource
from twisted.web import server

try:
    import json
except ImportError:
    import simplejson as json


class GitHubBuildBot(resource.Resource):

    """
    GitHubBuildBot creates the webserver that responds to the GitHub Service
    Hook.
    """
    isLeaf = True
    master = None
    port = None

    def render_POST(self, request):
        """
        Responds only to POST events and starts the build process

        :arguments:
            request
                the http request object
        """

        # All responses are application/json
        request.setHeader("Content-Type", "application/json")

        content = request.content.read()

        # Verify the message if a secret was provided
        #
        # NOTE: We always respond with '400 BAD REQUEST' if we can't
        # validate the message.  This is done to prevent malicious
        # requests from learning about why they failed to POST data
        # to us.
        if self.secret is not None:
            signature = request.getHeader("X-Hub-Signature")

            if signature is None:
                logging.error("Rejecting request.  Signature is missing.")
                request.setResponseCode(BAD_REQUEST)
                return json.dumps({"error": "Bad Request."})

            try:
                hash_type, hexdigest = signature.split("=")

            except ValueError:
                logging.error("Rejecting request.  Bad signature format.")
                request.setResponseCode(BAD_REQUEST)
                return json.dumps({"error": "Bad Request."})

            else:
                # sha1 is hard coded into github's source code so it's
                # unlikely this will ever change.
                if hash_type != "sha1":
                    logging.error("Rejecting request.  Unexpected hash type.")
                    request.setResponseCode(BAD_REQUEST)
                    return json.dumps({"error": "Bad Request."})

                mac = hmac.new(self.secret, msg=content, digestmod=sha1)
                if mac.hexdigest() != hexdigest:
                    logging.error("Rejecting request.  Hash mismatch.")
                    request.setResponseCode(BAD_REQUEST)
                    return json.dumps({"error": "Bad Request."})

        event_type = request.getHeader("X-GitHub-Event")
        logging.debug("X-GitHub-Event: %r", event_type)

        if event_type == "ping":
            request.setResponseCode(OK)
            return json.dumps({"result": "pong"})

        # Reject non-push, non-ping events
        if event_type != "push":
            logging.info(
                "Rejecting request.  Expected a push event but received %r instead.",
                event_type)
            request.setResponseCode(BAD_REQUEST)
            return json.dumps({"error": "Bad Request."})

        try:

            content_type = request.getHeader("Content-Type")

            if content_type == "application/json":
                payload = json.loads(content)
            elif content_type == "application/x-www-form-urlencoded":
                payload = json.loads(request.args["payload"][0])
            else:
                logging.info(
                    "Rejecting request.  Unknown 'Content-Type', received %r",
                    content_type)
                request.setResponseCode(BAD_REQUEST)
                return json.dumps({"error": "Bad Request."})

            logging.debug("Payload: %r", payload)
            user = payload['pusher']['name']
            repo = payload['repository']['name']
            repo_url = payload['repository']['url']
            self.private = payload['repository']['private']
            project = request.args.get('project', None)
            if project:
                project = project[0]
            self.process_change(payload, user, repo, repo_url, project, request)
            return server.NOT_DONE_YET

        except Exception, e:
            logging.exception(e)
            request.setResponseCode(INTERNAL_SERVER_ERROR)
            return json.dumps({"error": e.message})

    def process_change(self, payload, user, repo, repo_url, project, request):
        """
        Consumes the JSON as a python object and actually starts the build.

        :arguments:
            payload
                Python Object that represents the JSON sent by GitHub Service
                Hook.
        """
        changes = None
        branch = payload['ref'].split('/')[-1]

        if payload['deleted'] is True:
            logging.info("Branch %r deleted, ignoring", branch)
        else:
            changes = []

            for change in payload['commits']:
                files = change['added'] + change['removed'] + change['modified']
                who = "%s <%s>" % (
                    change['author']['username'], change['author']['email'])

                changes.append(
                    {'revision': change['id'],
                     'revlink': change['url'],
                     'who': who,
                     'comments': change['message'],
                     'repository': payload['repository']['url'],
                     'files': files,
                     'project': project,
                     'branch': branch})

        if not changes:
            logging.warning("No changes found")
            request.setResponseCode(OK)
            request.write(json.dumps({"result": "No changes found."}))
            request.finish()
            return

        host, port = self.master.split(':')
        port = int(port)

        if self.auth is not None:
            auth = credentials.UsernamePassword(*self.auth.split(":"))
        else:
            auth = credentials.Anonymous()

        factory = pb.PBClientFactory()
        deferred = factory.login(auth)
        reactor.connectTCP(host, port, factory)
        deferred.addErrback(self.connectFailed, request)
        deferred.addCallback(self.connected, changes, request)

    def connectFailed(self, error, request):
        """
        If connection is failed.  Logs the error.
        """
        logging.error("Could not connect to master: %s",
                      error.getErrorMessage())
        request.setResponseCode(INTERNAL_SERVER_ERROR)
        request.write(
            json.dumps({"error": "Failed to connect to buildbot master."}))
        request.finish()
        return error

    def addChange(self, _, remote, changei, src='git'):
        """
        Sends changes from the commit to the buildmaster.
        """
        logging.debug("addChange %r, %r", remote, changei)
        try:
            change = changei.next()
        except StopIteration:
            remote.broker.transport.loseConnection()
            return None

        logging.info("New revision: %s", change['revision'][:8])
        for key, value in change.iteritems():
            logging.debug("  %s: %s", key, value)

        change['src'] = src
        deferred = remote.callRemote('addChange', change)
        deferred.addCallback(self.addChange, remote, changei, src)
        return deferred

    def connected(self, remote, changes, request):
        """
        Responds to the connected event.
        """
        # By this point we've connected to buildbot so
        # we don't really need to keep github waiting any
        # longer
        request.setResponseCode(ACCEPTED)
        request.write(json.dumps({"result": "Submitting changes."}))
        request.finish()

        return self.addChange(None, remote, changes.__iter__())


def setup_options():
    """
    The main event loop that starts the server and configures it.
    """
    usage = "usage: %prog [options]"
    parser = OptionParser(usage)

    parser.add_option("-p", "--port",
                      help="Port the HTTP server listens to for the GitHub "
                           "Service Hook [default: %default]",
                      default=9001, type=int, dest="port")

    parser.add_option("-m", "--buildmaster",
                      help="Buildbot Master host and port. ie: localhost:9989 "
                           "[default: %default]",
                      default="localhost:9989", dest="buildmaster")

    parser.add_option("--auth",
                      help="The username and password, separated by a colon, "
                           "to use when connecting to buildbot over the "
                           "perspective broker.",
                      default="change:changepw", dest="auth")

    parser.add_option("--secret",
                      help="If provided then use the X-Hub-Signature header "
                           "to verify that the request is coming from "
                           "github. [default: %default]",
                      default=None, dest="secret")

    parser.add_option("-l", "--log",
                      help="The absolute path, including filename, to save the "
                           "log to [default: %default].  This may also be "
                           "'stdout' indicating logs should output directly to "
                           "standard output instead.",
                      default="github_buildbot.log", dest="log")

    parser.add_option("-L", "--level",
                      help="The logging level: debug, info, warn, error, "
                           "fatal [default: %default]", default='warn',
                      dest="level",
                      choices=("debug", "info", "warn", "error", "fatal"))

    parser.add_option("-g", "--github",
                      help="The github server.  Changing this is useful if"
                           " you've specified a specific HOST handle in "
                           "~/.ssh/config for github [default: %default]",
                      default='github.com', dest="github")

    parser.add_option("--pidfile",
                      help="Write the process identifier (PID) to this "
                           "file on start. The file is removed on clean "
                           "exit. [default: %default]",
                      default=None, dest="pidfile")

    (options, _) = parser.parse_args()

    if options.auth is not None and ":" not in options.auth:
        parser.error("--auth did not contain ':'")

    if options.pidfile:
        with open(options.pidfile, 'w') as f:
            f.write(str(os.getpid()))

    filename = options.log
    log_format = "%(asctime)s - %(levelname)s - %(message)s"
    if options.log != "stdout":
        logging.basicConfig(filename=filename, format=log_format,
                            level=logging._levelNames[options.level.upper()])
    else:
        logging.basicConfig(format=log_format,
                            handlers=[logging.StreamHandler(stream=sys.stdout)],
                            level=logging._levelNames[options.level.upper()])

    return options


def run_hook(options):
    github_bot = GitHubBuildBot()
    github_bot.github = options.github
    github_bot.master = options.buildmaster
    github_bot.secret = options.secret
    github_bot.auth = options.auth

    site = server.Site(github_bot)
    reactor.listenTCP(options.port, site)

    reactor.run()


def main():
    options = setup_options()

    run_hook(options)


if __name__ == '__main__':
    main()
