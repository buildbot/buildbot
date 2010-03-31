#!/usr/bin/python

"""Implements a sample server to receive status_push notifications.

It is mainly for testing.
Use with buildbot.status.status_push.StatusPush to receive all the buildbot
events.
"""

import logging
import optparse
import sys

try:
    from urlparse import parse_qs
except ImportError:
    from cgi import parse_qs

import BaseHTTPServer

try:
    import simplejson as json
except ImportError:
    try:
        import json
    except ImportError:
        # We can live without it.
        json = None


OPTIONS = None


class EventsHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            length = int(self.headers['Content-Length'])
        except (ValueError, KeyError):
            self.send_response(411)
            return

        try:
            if (self.headers['Content-Type'] !=
                    'application/x-www-form-urlencoded'):
                raise KeyError()
        except KeyError:
            self.send_response(406)
            return

        data = self.rfile.read(length)
        remaining = length - len(data)
        while remaining:
            data += self.rfile.read(remaining)
            remaining = length - len(data)

        data_dict = parse_qs(data, True)
        for packet in data_dict['packets']:
            if json != None:
                for p in json.loads(packet):
                    if OPTIONS.long:
                        print p
                    else:
                        print p['event']
            else:
                if OPTIONS.long:
                    print packet
                else:
                    print packet[:90] + '...'
        self.send_response(200, 'OK')
        self.send_header('Content-Type', 'text/plan')
        self.end_headers()
        self.wfile.write('OK')


def main(argv):
    parser = optparse.OptionParser(usage='%prog [options]\n\n' + __doc__)
    parser.add_option('-v', '--verbose', default=0, action='count',
                      help='Use multiple times to increase logging')
    parser.add_option('-p', '--port', type='int', default=8000,
                      help='HTTP port to bind to; default=%default')
    parser.add_option('-b', '--binding', default='',
                      help='IP address to bind, default=all')
    parser.add_option('-l', '--long', action='store_true',
                      help='Prints the whole packet')
    options, args = parser.parse_args(argv)

    if options.verbose == 0:
        logging.basicConfig(level=logging.ERROR)
    elif options.verbose == 1:
        logging.basicConfig(level=logging.WARNING)
    elif options.verbose == 2:
        logging.basicConfig(level=logging.INFO)
    else:
        logging.basicConfig(level=logging.DEBUG)

    global OPTIONS
    OPTIONS = options

    httpd = BaseHTTPServer.HTTPServer((options.binding, options.port),
                                      EventsHandler)
    if options.port == 0:
        options.port = httpd.server_port
    print 'Listening on port %d' % options.port
    sys.stdout.flush()
    httpd.serve_forever()


if __name__ == '__main__':
    sys.exit(main(sys.argv))

# vim: set ts=4 sts=4 sw=4 et:
