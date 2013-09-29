# use the 'requests' lib: http://python-requests.org

from buildbot.process.buildstep import BuildStep
from buildbot.process.buildstep import SUCCESS, FAILURE
from buildbot import config

import requests


class HTTPStep(BuildStep):

  name = 'HTTPStep'
  description = 'Requesting'
  descriptionDone = 'Requested'
  renderables = ['url', 'params', 'method', 'data', 'headers']

  def __init__(self, url, params=None, method='POST', data=None, headers=None,
               description=None, descriptionDone=None, **kwargs):
    BuildStep.__init__(self, **kwargs)
    self.url = url
    if params is None:
      self.params = {}
    else:
      self.params = params
    self.method = method.upper()
    if self.method not in ('POST', 'GET', 'PUT', 'DELETE', 'HEAD', 'OPTIONS'):
      config.error("Wrong method given: '%s' is not known" % self.method)
    if data is None:
      self.data = {}
    else:
      self.data = data
    if headers is None:
      self.headers = {}
    else:
      self.headers = headers
    if description is not None:
      self.description = description
    if descriptionDone is not None:
      self.descriptionDone = descriptionDone

  def start(self):
    log = self.addLog('log')
    func = {'POST'    : requests.post,
            'GET'     : requests.get,
            'PUT'     : requests.put,
            'DELETE'  : requests.delete,
            'HEAD'    : requests.head,
            'OPTIONS' : requests.options,
      }[self.method]

    log.addHeader('Performing %s request to %s\n' % (self.method, self.url))
    if self.params:
      log.addHeader('Parameters:\n')
      for k, v in self.params.iteritems():
        log.addHeader('\t%s: %s\n' % (k, v))

    if self.data:
      log.addHeader('Data:\n')
      if type(self.data) == dict:
        for k, v in self.data.iteritems():
          log.addHeader('\t%s: %s\n' % (k, v))
      else:
        log.addHeader('\t%s\n' % self.data)


    try:
      r = func(self.url, params=self.params, data=self.data, headers=self.headers)
    except requests.exceptions.ConnectionError, e:
      log.addStderr('An exception occured while performing the request: %s' % e)
      self.finished(FAILURE)
      return

    if r.history:
      log.addStdout('\nRedirected %d times:\n\n' % len(r.history))
      for rr in r.history:
        self.log_request(rr)
        log.addStdout('=' * 60 + '\n')

    self.log_request(r)

    log.finish()

    self.step_status.setText(self.describe(done=True))
    if (r.status_code < 400):
      self.finished(SUCCESS)
    else:
      self.finished(FAILURE)

  def log_request(self, request):
    log = self.getLog('log')

    log.addHeader('Request Header:\n')
    for k, v in request.request.headers.iteritems():
      log.addHeader('\t%s: %s\n' % (k, v))

    log.addStdout('URL: %s\n' % request.url)

    if request.status_code == requests.codes.ok:
      log.addStdout('Status: %s\n' % request.status_code)
    else:
      log.addStderr('Status: %s\n' % request.status_code)

    log.addHeader('Response Header:\n')
    for k, v in request.headers.iteritems():
      log.addHeader('\t%s: %s\n' % (k, v))

    log.addStdout(' ------ Content ------\n%s' % request.text)

  def describe(self, done=False):
    if done:
      return self.descriptionDone.split()
    return self.description.split()

class POST(HTTPStep):
  def __init__(self, url, **kwargs):
    HTTPStep.__init__(self, url, method='POST', **kwargs)

class GET(HTTPStep):
  def __init__(self, url, **kwargs):
    HTTPStep.__init__(self, url, method='GET', **kwargs)

class PUT(HTTPStep):
  def __init__(self, url, **kwargs):
    HTTPStep.__init__(self, url, method='PUT', **kwargs)

class DELETE(HTTPStep):
  def __init__(self, url, **kwargs):
    HTTPStep.__init__(self, url, method='DELETE', **kwargs)

class HEAD(HTTPStep):
  def __init__(self, url, **kwargs):
    HTTPStep.__init__(self, url, method='HEAD', **kwargs)

class OPTIONS(HTTPStep):
  def __init__(self, url, **kwargs):
    HTTPStep.__init__(self, url, method='OPTIONS', **kwargs)

