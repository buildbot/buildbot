#!/usr/bin/env python
"""check_buildbot.py -H hostname -p httpport [options]

nagios check for buildbot.

requires that both metrics and web status enabled.

Both hostname and httpport must be set, or alternatively use url which
should be the full url to the metrics json resource"""
try:
    import simplejson as json
except ImportError:
    import json

import sys
import urllib

OK, WARNING, CRITICAL, UNKNOWN = range(4)
STATUS_TEXT = ["OK", "Warning", "Critical", "Unknown"]
STATUS_CODES = dict(OK=OK, WARNING=WARNING, CRIT=CRITICAL)


def exit(level, msg):
    print "%s: %s" % (STATUS_TEXT[level], msg)
    sys.exit(level)


def main():
    from optparse import OptionParser
    parser = OptionParser(__doc__)
    parser.set_defaults(
        hostname=None,
        httpport=None,
        url=None,
        verbosity=0
    )
    parser.add_option("-H", "--host", dest="hostname",
                      help="Hostname")
    parser.add_option("-p", "--port", dest="httpport",
                      type="int", help="WebStatus port")
    parser.add_option("-u", "--url", dest="url",
                      help="Metrics url")
    parser.add_option("-v", "--verbose", dest="verbosity",
                      action="count", help="Increase verbosity")
    options, args = parser.parse_args()

    if options.hostname and options.httpport:
        url = "http://%s:%s/json/metrics" % (options.hostname, options.httpport)
    elif options.url:
        url = options.url
    else:
        exit(UNKNOWN, "You must specify both hostname and httpport, or just url")

    try:
        data = urllib.urlopen(url).read()
    except Exception:
        exit(CRITICAL, "Error connecting to %s" % url)

    try:
        data = json.loads(data)
    except ValueError:
        exit(CRITICAL, "Could not parse output of %s as json" % url)

    if not data:
        exit(WARNING, "%s returned null; are metrics disabled?" % url)

    alarms = data['alarms']
    status = OK
    messages = []
    for alarm_name, alarm_state in alarms.items():
        if options.verbosity >= 2:
            messages.append("%s: %s" % (alarm_name, alarm_state))

        try:
            alarm_code = STATUS_CODES[alarm_state[0]]
        except (KeyError, IndexError):
            status = UNKNOWN
            messages.append("%s has unknown alarm state %s" % (alarm_name, alarm_state))
            continue

        status = max(status, alarm_code)
        if alarm_code > OK and options.verbosity < 2:
            messages.append("%s: %s" % (alarm_name, alarm_state))

    if not messages and status == OK:
        messages.append("no problems")
    exit(status, ";".join(messages))

if __name__ == '__main__':
    main()
