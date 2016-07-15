"""
Send build results of builds to Atlassian Stash.

https://developer.atlassian.com/stash/docs/latest/how-tos/updating-build-status-for-commits.html
"""

from base64 import b64encode
from buildbot.interfaces import IStatusReceiver
from buildbot.process.properties import Interpolate
from buildbot.status.base import StatusReceiverMultiService
from buildbot.status.builder import SUCCESS
from buildbot.status.buildset import BuildSetSummaryNotifierMixin
from json import dumps
from twisted.web.client import Agent
from twisted.web.http_headers import Headers
from twisted.web.iweb import IBodyProducer
from twisted.internet import reactor, defer
from twisted.python import log
from zope.interface import implements

try:
    from twisted.web.client import readBody
except ImportError:
    def readBody(*args, **kwargs):
        return defer.succeed('StatusStashPush requires '
                             'twisted.web.client.readBody() '
                             'to report the body of Stash API errors. '
                             'Please upgrade to Twisted 13.1.0 or newer '
                             'if you need more verbose error messages.')

# Magic words understood by Stash REST API
INPROGRESS = 'INPROGRESS'
SUCCESSFUL = 'SUCCESSFUL'
FAILED = 'FAILED'


def logIfNot2XX(response):
    """
    If we get a response other than 200, 204, or other success,
    log it.
    """
    if 200 < response.code <= 300:
        return

    def cbBody(body):
        error_message = 'StashStatusPush received %s with body: %s'
        log.err(error_message % (response.code, body))

    d = readBody(response)
    d.addCallback(cbBody)
    return d


class StringProducer(object):
    implements(IBodyProducer)

    def __init__(self, body):
        self.body = body
        self.length = len(body)

    def startProducing(self, consumer):
        consumer.write(self.body)
        return defer.succeed(None)

    def pauseProducing(self):
        pass

    def stopProducing(self):
        pass


class StashStatusPush(StatusReceiverMultiService,
                      BuildSetSummaryNotifierMixin):
    implements(IStatusReceiver)

    def __init__(self, base_url, user, password,
                 key_format='%(prop:builderName)s',
                 name_format=None):
        """
        :param base_url: The base url of the stash host, up to the path.
        For example, https://stash.example.com/
        :param user: The stash user to log in as using http basic auth.
        :param password: The password to use with the stash user.
        :param key_format: A rendered string used as
            the build status key sent to Stash.
            Defaults to '%(prop:builderName)s' for backwards compatability.
        :param name_format: A rendered string used as
            the build status name sent to stash.
            Defaults to None, which disables sending it.
        :return:
        """
        StatusReceiverMultiService.__init__(self)
        if not base_url.endswith('/'):
            base_url += '/'
        self.base_url = '%srest/build-status/1.0/commits/' % (base_url, )
        self.auth = b64encode('%s:%s' % (user, password))
        self.key_interpolation = Interpolate(key_format)
        self.name_interpolation = Interpolate(name_format or '')
        self.name_format = name_format
        self._sha = Interpolate('%(src::revision)s')
        self.master_status = None

    def _send(self, request_kwargs, body, error_message):
        request_kwargs['bodyProducer'] = StringProducer(body)
        agent = Agent(reactor)
        d = agent.request(**request_kwargs)
        d.addCallback(logIfNot2XX)
        d.addErrback(log.err, error_message)
        return d

    @defer.inlineCallbacks
    def send(self, builderName, build, status):
        sha, key, name_string = yield defer.gatherResults([
            build.render(self._sha),
            build.render(self.key_interpolation),
            build.render(self.name_interpolation),
        ])
        build_url = build.builder.status.getURLForThing(build)
        body_dict = {'state': status, 'key': key, 'url': build_url}
        if self.name_format is not None:
            body_dict['name'] = name_string
        body = dumps(body_dict)
        stash_uri = self.base_url + sha
        request_kwargs = dict(
            method='POST',
            uri=bytes(stash_uri),
            headers=Headers({
                'Content-Type': ['application/json; charset=utf-8', ],
                'Authorization': ['Basic %s' % (self.auth, ), ],
                'Accept': ['*/*', ],
                'Accept-Language': ['en-US, en;q=0.8', ],
            })
        )
        error_message = 'StashStatusPush failed while POSTing status message ' \
                        'for commit %s built by builder %s to %s with body %r' \
                        '' % (sha, builderName, stash_uri, body)
        yield self._send(request_kwargs, body, error_message)

    def setServiceParent(self, parent):
        """
        @type  parent: L{buildbot.master.BuildMaster}
        """
        StatusReceiverMultiService.setServiceParent(self, parent)
        self.master_status = self.parent
        self.master_status.subscribe(self)
        self.master = self.master_status.master

    def startService(self):
        print """Starting up StashStatusPush"""
        self.summarySubscribe()
        StatusReceiverMultiService.startService(self)

    def stopService(self):
        self.summaryUnsubscribe()

    def builderAdded(self, name, builder):
        return self

    def buildStarted(self, builderName, build):
        self.send(builderName, build, INPROGRESS)
        return self

    def buildFinished(self, builderName, build, results):
        self.send(builderName, build,
                  SUCCESSFUL if results == SUCCESS else FAILED)
        return self

    # necessary methods to satisfy implements()
    def sendBuildSetSummary(self, buildset, builds):
        pass

    def sendCodeReviews(self, build, result):
        pass

    def sendCodeReview(self, project, revision, result):
        pass
