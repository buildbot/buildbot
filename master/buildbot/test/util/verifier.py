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

import datetime
from buildbot.util import json
from buildbot.data import base

def _dictProblems(value, typename, attrs):
    # helper functions
    def orNone(valfn):
        return lambda v : v is None or valfn(v)

    def stringlist(value):
        if not isinstance(value, list):
            return False
        for x in value:
            if not isinstance(x, unicode):
                return False
        return True

    def sourcedProperties(value):
        if not isinstance(value, dict):
            return False
        for k, v in value.iteritems():
            if not isinstance(k, unicode):
                return False
            if not isinstance(v, tuple):
                return False
            if not 2 == len(v):
                return False
            propval, propsrc = v
            if not isinstance(propsrc, unicode):
                return False
            try:
                json.dumps(propval)
            except:
                return False
        return True

    validators = {}
    for name, typ in attrs.iteritems():
        noneok = typ.endswith(':none')
        if noneok:
            typ = typ[:-5]
        if ':' in typ:
            typ, rest = typ.split(':', 1)
        else:
            rest = ''

        if typ == 'integer':
            valfn = lambda v : isinstance(v, int)
        elif typ == 'string':
            # note that we intentionally *enforce* unicode!
            valfn = lambda v : isinstance(v, unicode)
        elif typ == 'stringlist':
            valfn = stringlist
        elif typ == 'sourcedProperties':
            valfn = sourcedProperties
        elif typ == 'Link':
            valfn = lambda v : isinstance(v, base.Link)
        elif typ == 'datetime':
            valfn = lambda v : isinstance(v, datetime.datetime)
        elif typ == 'enum':
            vals = set(rest.split(','))
            valfn = lambda v : isinstance(v, unicode) and v in vals
        else:
            raise RuntimeError('invalid type %s' % typ)

        validators[name] = orNone(valfn) if noneok else valfn

    problems = []

    if not isinstance(value, dict):
        problems.append("not a dictionary")
        return problems

    res_keys = set(value)
    exp_keys = set(attrs)
    if res_keys != exp_keys:
        unk_keys = res_keys - exp_keys
        missing_keys = exp_keys - res_keys
        if unk_keys:
            problems.append("unknown key%s %s"
                % ('s' if len(unk_keys) > 1 else '',
                    ', '.join(map(repr, unk_keys))))
        if missing_keys:
            problems.append("missing key%s %s"
                % ('s' if len(missing_keys) > 1 else '',
                    ', '.join(map(repr, missing_keys))))

    for k in res_keys & exp_keys:
        if not validators[k](value[k]):
            problems.append('value %r for "%s" does not match type %s' %
                    (value[k], k, attrs[k]))

    return problems


def _routingKeyProblems(routingKey, message, typename, keyFields, events):
    problems = []
    if not isinstance(routingKey, tuple) or len(routingKey) < 2:
        problems.append("ill-formed routing key")
        return problems

    if routingKey[0] != typename:
        problems.append("routing key's first element is not '%s'"
                % (typename,))
    if routingKey[-1] not in events:
        problems.append("routing key's last element is not a known event")
    if len(routingKey) != len(keyFields) + 2:
        problems.append("routing key does not have expected length (%d)"
                % (len(keyFields)+2,))
        return problems

    for i, f in enumerate(keyFields):
        j = i + 1
        pfx = "routingKey[%d]: " % (j,)
        if f not in message:
            problems.append(pfx + "no such value in message")
            continue
        if str(message[f]) != routingKey[j]:
            problems.append(pfx + "value in message does not match")

    return problems

def verifyDict(testcase, value, typename, attrs):
    problems = _dictProblems(value, typename, attrs)

    if problems:
        msg = "%r is not a %s: " % (value, typename,)
        msg += '; '.join(problems)
        testcase.fail(msg)

def verifyMessage(testcase, routingKey, message,
        typename, keyFields, events, attrs):

    keyProblems = _routingKeyProblems(routingKey, message, typename,
                                        keyFields, events)
    msgProblems = _dictProblems(message, typename, attrs)

    problems = keyProblems + msgProblems

    if problems:
        msg = "%r / %r is not a %s message: " \
                % (routingKey, message, typename)
        msg += '; '.join(problems)
        testcase.fail(msg)
