#!/usr/bin/env python
"""Change source forwarder for bitbucket.org POST service.

bitbucket_buildbot.py will determine the repository information from
the JSON HTTP POST it receives from bitbucket.org and build the
appropriate repository.

If your bitbucket repository is private, you must add a ssh key to the
bitbucket repository for the user who initiated bitbucket_buildbot.py

bitbucket_buildbot.py is based on github_buildbot.py
"""

import logging
from optparse import OptionParser
import sys
import tempfile
import traceback

from twisted.web import server, resource
from twisted.internet import reactor
from twisted.spread import pb
from twisted.cred import credentials

try:
    import json
except ImportError:
    import simplejson as json


class BitBucketBuildBot(resource.Resource):
    """
    BitBucketBuildBot creates the webserver that responds to the
    BitBucket POST Service Hook.
    """
    isLeaf = True
    bitbucket = None
    master = None
    port = None
    private = False

    def render_POST(self, request):
        """
        Reponds only to POST events and starts the build process

        :arguments:
            request
                the http request object
        """
        try:
            payload = json.loads(request.args['payload'][0])
            logging.debug("Payload: " + str(payload))
            self.process_change(payload)
        except Exception:
            logging.error("Encountered an exception:")
            for msg in traceback.format_exception(*sys.exc_info()):
                logging.error(msg.strip())

    def process_change(self, payload):
        """
        Consumes the JSON as a python object and actually starts the build.

        :arguments:
            payload
                Python Object that represents the JSON sent by Bitbucket POST
                Service Hook.
        """
        if self.private:
            repo_url = 'ssh://hg@%s%s' % (
                self.bitbucket,
                payload['repository']['absolute_url'],
                )
        else:
            repo_url = 'http://%s%s' % (
                self.bitbucket,
                payload['repository']['absolute_url'],
                )
        changes = []
        for commit in payload['commits']:
            files = [file_info['file'] for file_info in commit['files']]
            revlink = 'http://%s%s/changeset/%s/' % (
                self.bitbucket,
                payload['repository']['absolute_url'],
                commit['node'],
                )
            change = {
                'revision': commit['node'],
                'revlink': revlink,
                'comments': commit['message'],
                'who': commit['author'],
                'files': files,
                'links': [revlink],
                'properties': dict(repository=repo_url),
                }
            changes.append(change)
        # Submit the changes, if any
        if not changes:
            logging.warning("No changes found")
            return
        host, port = self.master.split(':')
        port = int(port)
        factory = pb.PBClientFactory()
        deferred = factory.login(credentials.UsernamePassword("change",
                                                              "changepw"))
        reactor.connectTCP(host, port, factory)
        deferred.addErrback(self.connectFailed)
        deferred.addCallback(self.connected, changes)

    def connectFailed(self, error):
        """
        If connection is failed.  Logs the error.
        """
        logging.error("Could not connect to master: %s"
                % error.getErrorMessage())
        return error

    def addChange(self, dummy, remote, changei):
        """
        Sends changes from the commit to the buildmaster.
        """
        logging.debug("addChange %s, %s" % (repr(remote), repr(changei)))
        try:
            change = changei.next()
        except StopIteration:
            remote.broker.transport.loseConnection()
            return None

        logging.info("New revision: %s" % change['revision'][:8])
        for key, value in change.iteritems():
            logging.debug("  %s: %s" % (key, value))

        deferred = remote.callRemote('addChange', change)
        deferred.addCallback(self.addChange, remote, changei)
        return deferred

    def connected(self, remote, changes):
        """
        Reponds to the connected event.
        """
        return self.addChange(None, remote, changes.__iter__())


def main():
    """
    The main event loop that starts the server and configures it.
    """
    usage = "usage: %prog [options]"
    parser = OptionParser(usage)
    parser.add_option(
        "-p", "--port",
        help="Port the HTTP server listens to for the Bitbucket Service Hook"
        " [default: %default]", default=4000, type=int, dest="port")
    parser.add_option(
        "-m", "--buildmaster",
        help="Buildbot Master host and port. ie: localhost:9989 [default:"
        + " %default]", default="localhost:9989", dest="buildmaster")
    parser.add_option(
        "-l", "--log",
        help="The absolute path, including filename, to save the log to"
        " [default: %default]",
        default = tempfile.gettempdir() + "/bitbucket_buildbot.log",
        dest="log")
    parser.add_option(
        "-L", "--level",
        help="The logging level: debug, info, warn, error, fatal [default:"
        " %default]", default='warn', dest="level")
    parser.add_option(
        "-g", "--bitbucket",
        help="The bitbucket serve [default: %default]",
        default='bitbucket.org',
        dest="bitbucket")
    parser.add_option(
        '-P', '--private',
        help='Use SSH to connect, for private repositories.',
        dest='private',
        default=False,
        action='store_true',
        )
    (options, _) = parser.parse_args()
    # Set up logging.
    levels = {
        'debug': logging.DEBUG,
        'info': logging.INFO,
        'warn': logging.WARNING,
        'error': logging.ERROR,
        'fatal': logging.FATAL,
        }
    filename = options.log
    log_format = "%(asctime)s - %(levelname)s - %(message)s"
    logging.basicConfig(filename=filename, format=log_format,
                        level=levels[options.level])
    # Start listener.
    bitbucket_bot = BitBucketBuildBot()
    bitbucket_bot.bitbucket = options.bitbucket
    bitbucket_bot.master = options.buildmaster
    bitbucket_bot.private = options.private
    site = server.Site(bitbucket_bot)
    reactor.listenTCP(options.port, site)
    reactor.run()


if __name__ == '__main__':
    main()
