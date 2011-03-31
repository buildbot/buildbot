import urllib

from twisted.python import log
from twisted.internet import reactor
from twisted.web import client, error

from buildbot import status

MAX_ATTEMPTS     = 10
RETRY_MULTIPLIER = 5

class WebHookTransmitter(status.base.StatusReceiverMultiService):
    """
    A webhook status listener for buildbot.

    WebHookTransmitter listens for build events and sends the events
    as http POSTs to one or more webhook URLs.

    The easiest way to deploy this is to place it next to your
    master.cfg and do something like this (assuming you've got a
    postbin URL for purposes of demonstration):

      from webhook_status import WebHookTransmitter
      c['status'].append(WebHookTransmitter('http://www.postbin.org/xxxxxxx'))

    Alternatively, you may provide a list of URLs and each one will
    receive information on every event.

    The following optional parameters influence when and what data is
    transmitted:

    categories:       If provided, only events belonging to one of the
                      categories listed will be transmitted.

    extra_params:     Additional parameters to be supplied with every request.

    max_attempts:     The maximum number of times to retry transmission
                      on failure.          Default: 10

    retry_multiplier: A value multiplied by the retry number to wait before
                      attempting a retry.  Default 5
    """

    agent = 'buildbot webhook'

    def __init__(self, url, categories=None, extra_params={},
                 max_attempts=MAX_ATTEMPTS, retry_multiplier=RETRY_MULTIPLIER):
        status.base.StatusReceiverMultiService.__init__(self)
        if isinstance(url, basestring):
            self.urls = [url]
        else:
            self.urls = url
        self.categories = categories
        self.extra_params = extra_params
        self.max_attempts = max_attempts
        self.retry_multiplier = retry_multiplier

    def _transmit(self, event, params={}):

        cat = dict(params).get('category', None)
        if (cat and self.categories) and cat not in self.categories:
            log.msg("Ignoring request for unhandled category:  %s" % cat)
            return

        new_params = [('event', event)]
        new_params.extend(list(self.extra_params.items()))
        if hasattr(params, "items"):
            new_params.extend(params.items())
        else:
            new_params.extend(params)
        encoded_params = urllib.urlencode(new_params)

        log.msg("WebHookTransmitter announcing a %s event" % event)
        for u in self.urls:
            self._retrying_fetch(u, encoded_params, event, 0)

    def _retrying_fetch(self, u, data, event, attempt):
        d = client.getPage(u, method='POST', agent=self.agent,
                           postdata=data, followRedirect=0)

        def _maybe_retry(e):
            log.err()
            if attempt < self.max_attempts:
                reactor.callLater(attempt * self.retry_multiplier,
                                  self._retrying_fetch, u, data, event, attempt + 1)
            else:
                return e

        def _trap_status(x, *acceptable):
            x.trap(error.Error)
            if int(x.value.status) in acceptable:
                log.msg("Terminating retries of event %s with a %s response"
                        % (event, x.value.status))
                return None
            else:
                return x

        # Any sort of redirect is considered success
        d.addErrback(lambda x: x.trap(error.PageRedirect))

        # Any of these status values are considered delivered, or at
        # least not something that should be retried.
        d.addErrback(_trap_status,
                     # These are all actually successes
                     201, 202, 204,
                     # These tell me I'm sending stuff it doesn't want.
                     400, 401, 403, 405, 406, 407, 410, 413, 414, 415,
                     # This tells me the server can't deal with what I sent
                     501)

        d.addCallback(lambda x: log.msg("Completed %s event hook on attempt %d" %
                                        (event, attempt+1)))
        d.addErrback(_maybe_retry)
        d.addErrback(lambda e: log.err("Giving up delivering %s to %s" % (event, u)))

    def builderAdded(self, builderName, builder):
        builder.subscribe(self)
        self._transmit('builderAdded',
                       {'builder': builderName,
                        'category': builder.getCategory()})

    def builderRemoved(self, builderName, builder):
        self._transmit('builderRemoved',
                       {'builder': builderName,
                        'category': builder.getCategory()})

    def buildStarted(self, builderName, build):
        build.subscribe(self)

        args = {'builder': builderName,
                'category': build.getBuilder().getCategory(),
                'reason': build.getReason(),
                'revision': build.getSourceStamp().revision,
                'buildNumber': build.getNumber()}

        if build.getSourceStamp().patch:
            args['patch'] = build.getSourceStamp().patch[1]

        self._transmit('buildStarted', args)

    def buildFinished(self, builderName, build, results):
        self._transmit('buildFinished',
                       {'builder': builderName,
                        'category': build.getBuilder().getCategory(),
                        'result': status.builder.Results[results],
                        'revision': build.getSourceStamp().revision,
                        'had_patch': bool(build.getSourceStamp().patch),
                        'buildNumber': build.getNumber()})

    def stepStarted(self, build, step):
        step.subscribe(self)
        self._transmit('stepStarted',
                       [('builder', build.getBuilder().getName()),
                        ('category', build.getBuilder().getCategory()),
                        ('buildNumber', build.getNumber()),
                        ('step', step.getName())])

    def stepFinished(self, build, step, results):
        gu = self.status.getURLForThing
        self._transmit('stepFinished',
                       [('builder', build.getBuilder().getName()),
                        ('category', build.getBuilder().getCategory()),
                        ('buildNumber', build.getNumber()),
                        ('resultStatus', status.builder.Results[results[0]]),
                        ('resultString', ' '.join(results[1])),
                        ('step', step.getName())]
                       + [('logFile', gu(l)) for l in step.getLogs()])

    def _subscribe(self):
        self.status.subscribe(self)

    def setServiceParent(self, parent):
        status.base.StatusReceiverMultiService.setServiceParent(self, parent)
        self.status = parent.getStatus()

        self._transmit('startup')

        self._subscribe()
