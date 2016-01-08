'''
Logentries Status plugin for buildbot

This plugin sends a subset of status updates to the Logentries service.

Usage:

    import logentries
    c['status'].append(logentries.LogentriesStatusPush(api_token="da45d4be-e1e7-4de3-9861-45bdab564cb3", endpoint="data.logentries.com", port=10000))

If you want SSL

    import logentries
    c['status'].append(logentries.LogentriesStatusPush(api_token="da45d4be-e1e7-4de3-9861-45bdab564cb3", endpoint="data.logentries.com", port=20000, tls=True))
'''

from buildbot.status.base import StatusReceiverMultiService
from buildbot.status.builder import Results, SUCCESS
import os, urllib, json, requests
import certifi
import ssl
import socket
import codecs
import random
import time


def _to_unicode(ch):
    return codecs.unicode_escape_decode(ch)[0]


def _is_unicode(ch):
    return isinstance(ch, unicode)


def _create_unicode(ch):
    return unicode(ch, 'utf-8')


class PlainTextSocketAppender(object):
    def __init__(self,
                 verbose=True,
                 LE_API='data.logentries.com',
                 LE_PORT=80,
                 LE_TLS_PORT=443):

        self.LE_API = LE_API
        self.LE_PORT = LE_PORT
        self.LE_TLS_PORT = LE_TLS_PORT
        self.MIN_DELAY = 0.1
        self.MAX_DELAY = 10
        # Error message displayed when an incorrect Token has been detected
        self.INVALID_TOKEN = ("\n\nIt appears the LOGENTRIES_TOKEN "
                              "parameter you entered is incorrect!\n\n")
        # Unicode Line separator character   \u2028
        self.LINE_SEP = _to_unicode(r'\u2028')

        self.verbose = verbose
        self._conn = None

    def open_connection(self):
        self._conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self._conn.connect((self.LE_API, self.LE_PORT))
        except Exception, e:
            print("Error %s".format(e))

    def reopen_connection(self):
        self.close_connection()

        root_delay = self.MIN_DELAY
        while True:
            try:
                self.open_connection()
                return
            except Exception:
                if self.verbose:
                    print('Unable to connect to Logentries')

            root_delay *= 2
            if root_delay > self.MAX_DELAY:
                root_delay = self.MAX_DELAY

            wait_for = root_delay + random.uniform(0, root_delay)

            try:
                time.sleep(wait_for)
            except KeyboardInterrupt:
                raise

    def close_connection(self):
        if self._conn is not None:
            self._conn.close()

    def put(self, data):
        # Replace newlines with Unicode line separator
        # for multi-line events
        if not _is_unicode(data):
            multiline = _create_unicode(data).replace('\n', self.LINE_SEP)
        else:
            multiline = data.replace('\n', self.LINE_SEP)
        multiline += "\n"
        # Send data, reconnect if needed
        while True:
            try:
                self._conn.send(multiline.encode('utf-8'))
            except socket.error:
                self.reopen_connection()
                continue
            break

        self.close_connection()


try:
    import ssl
    HAS_SSL = True
except ImportError:  # for systems without TLS support.
    SocketAppender = PlainTextSocketAppender
    HAS_SSL = False
else:

    class TLSSocketAppender(PlainTextSocketAppender):
        def open_connection(self):
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock = ssl.wrap_socket(
                sock=sock,
                keyfile=None,
                certfile=None,
                server_side=False,
                cert_reqs=ssl.CERT_REQUIRED,
                ssl_version=getattr(
                    ssl, 'PROTOCOL_TLSv1_2', ssl.PROTOCOL_TLSv1),
                ca_certs=certifi.where(),
                do_handshake_on_connect=True,
                suppress_ragged_eofs=True, )
            sock.connect((self.LE_API, self.LE_TLS_PORT))
            self._conn = sock

    SocketAppender = TLSSocketAppender


class LogentriesStatusPush(StatusReceiverMultiService):

    def __init__(self, api_token, localhost_replace=False, endpoint='data.logentries.com', port=10000, tls=False, **kwargs):
        StatusReceiverMultiService.__init__(self)

        self.api_token = api_token
        self.localhost_replace = localhost_replace
        self.endpoint = endpoint
        self.port = port
        self.tls = tls
        self.appender = self._get_appender(endpoint, port, tls)
        self.appender.reopen_connection()

    def _get_appender(self,
                      endpoint='data.logentries.com',
                      port=10000,
                      tls=False):
        if tls:
            return TLSSocketAppender(verbose=False,
                                     LE_API=endpoint,
                                     LE_PORT=port)
        else:
            return PlainTextSocketAppender(verbose=False,
                                           LE_API=endpoint,
                                           LE_PORT=port)

    def _emit(self, token, msg):
        return '{0} {1}'.format(token, msg)

    def sendNotification(self, message):
        self.appender.put(self._emit(self.api_token, message))

    def setServiceParent(self, parent):
        StatusReceiverMultiService.setServiceParent(self, parent)
        self.master_status = self.parent
        self.master_status.subscribe(self)
        self.master = self.master_status.master

    def disownServiceParent(self):
        self.master_status.unsubscribe(self)
        self.master_status = None
        for w in self.watched:
            w.unsubscribe(self)
        return StatusReceiverMultiService.disownServiceParent(self)

    def builderAdded(self, name, builder):
        return self  # subscribe to this builder

    def buildFinished(self, builderName, build, result):
        url = self.master_status.getURLForThing(build)
        if self.localhost_replace:
            url = url.replace("//localhost", "//%s" % self.localhost_replace)

        reason = build.getReason()

        message = "url=%s buildername=%s result=%s reason='%s'" % (
            url, builderName, Results[result].upper(), reason)

        self.sendNotification(message)

    def buildStarted(self, builderName, build):
        url = self.master_status.getURLForThing(build)
        if self.localhost_replace:
            url = url.replace("//localhost", "//%s" % self.localhost_replace)

        reason = build.getReason()

        message = "url=%s buildername=%s result=STARTED reason='%s'" % (
            url, builderName, reason)

        self.sendNotification(message)
