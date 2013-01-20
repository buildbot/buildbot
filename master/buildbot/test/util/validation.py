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

# See "Type Validation" in master/docs/developer/tests.rst

from buildbot.util import json, UTC
from buildbot.data import base
import datetime

# Base class

class Validator(object):

    def validate(self, name, object):
        raise NotImplementedError

# Basic types

class InstanceValidator(Validator):
    types = ()
    name = ''

    def validate(self, name, object):
        if not isinstance(object, self.types):
            yield "%s (%r) is not a %s" % (
                    name, object, self.name or `self.types`)

class IntValidator(InstanceValidator):
    types = (int, long)
    name = 'integer'

class BooleanValidator(InstanceValidator):
    types = (bool,)
    name = 'boolean'

class LinkValidator(InstanceValidator):
    types = (base.Link,)
    name = 'Link'

class StringValidator(InstanceValidator):
    # note that unicode is *required* for strings
    types = (unicode,)
    name = 'unicode string'

class BinaryValidator(InstanceValidator):
    types = (str,)
    name = 'bytestring'

class DateTimeValidator(Validator):
    types = (datetime.datetime,)
    name = 'datetime'

    def validate(self, name, object):
        if not isinstance(object, datetime.datetime):
            yield "%s - %r - is not a datetime" % (name, object)
        elif object.tzinfo != UTC:
            yield "%s is not a UTC datetime" % (name,)

# Miscellaneous

class NoneOk(object):

    def __init__(self, original):
        self.original = original

    def validate(self, name, object):
        if object is None:
            return
        else:
            for msg in self.original.validate(name, object):
                yield msg

class Any(object):

    def validate(self, name, object):
        return

# Compound Types

class DictValidator(Validator):

    def __init__(self, optionalNames=[], **keys):
        self.optionalNames = set(optionalNames)
        self.keys = keys
        self.expectedNames = set(keys.keys())

    def validate(self, name, object):
        # this uses isinstance, allowing dict subclasses as used by the DB API
        if not isinstance(object, dict):
            yield "%s (%r) is not a dictionary (got type %s)" \
                    % (name, object, type(object))
            return

        gotNames = set(object.keys())

        unexpected = gotNames - self.expectedNames
        if unexpected:
            yield "%s has unexpected keys %s" % (name,
                    ", ".join([ `n` for n in unexpected ]))

        missing = self.expectedNames - self.optionalNames - gotNames
        if missing:
            yield "%s is missing keys %s" % (name,
                    ", ".join([ `n` for n in missing ]))

        for k in gotNames & self.expectedNames:
            for msg in self.keys[k].validate("%s[%r]" % (name, k), object[k]):
                yield msg

class SequenceValidator(Validator):
    type = None
    name = ''

    def __init__(self, elementValidator):
        self.elementValidator = elementValidator

    def validate(self, name, object):
        if type(object) != self.type:
            yield "%s (%r) is not a %s" % (name, object, self.name)
            return

        for idx, elt in enumerate(object):
            for msg in self.elementValidator.validate("%s[%d]" % (name, idx),
                                                      elt):
                yield msg

class ListValidator(SequenceValidator):
    type = list
    name = 'list'

class TupleValidator(SequenceValidator):
    type = tuple
    name = 'tuple'

class SourcedPropertiesValidator(Validator):

    def validate(self, name, object):
        if type(object) != dict:
            yield "%s is not sourced properties (not a dict)" % (name,)
            return
        for k, v in object.iteritems():
            if not isinstance(k, unicode):
                yield "%s property name %r is not unicode" % (name, k)
            if not isinstance(v, tuple) or len(v) != 2:
                yield "%s property value for '%s' is not a 2-tuple" % (name, k)
                return
            propval, propsrc = v
            if not isinstance(propsrc, unicode):
                yield "%s[%s] source %r is not unicode" % (name, k, propsrc)
            try:
                json.dumps(propval)
            except:
                yield "%s[%r] value is not JSON-able" % (name, k)

class MessageValidator(Validator):

    routingKeyValidator = TupleValidator(BinaryValidator())

    def __init__(self, keyFields, events, messageValidator):
        self.keyFields = keyFields
        self.events = set(events)
        self.messageValidator = messageValidator

    def validate(self, name, routingKey_message):
        try:
            routingKey, message = routingKey_message
        except (TypeError, ValueError) as e:
            yield "%r: not a routing key and message: %s" % (routingKey_message, e)
        routingKeyBad = False
        for msg in self.routingKeyValidator.validate("routingKey", routingKey):
            yield msg
            routingKeyBad = True

        if not routingKeyBad:
            event = routingKey[-1]
            if event not in self.events:
                yield "routing key event %r is not valid" % (event,)
            if len(routingKey) != len(self.keyFields) + 2:
                yield "routing key length is wrong"
            for i, f in enumerate(self.keyFields):
                j = i + 1
                pfx = "routingKey[%d]" % (j,)
                if f not in message:
                    yield "%s: no field '%s in message" % (pfx, f)
                elif str(message[f]) != routingKey[j]:
                    yield ("%s: routing key value for %s (%s) does not match "
                        "message (%s)" % (pfx, f, routingKey[j], message[f]))

        for msg in self.messageValidator.validate("%s message" % routingKey[0],
                                                  message):
            yield msg

class Selector(Validator):

    def __init__(self):
        self.selectors = []

    def add(self, selector, validator):
        self.selectors.append((selector, validator))

    def validate(self, name, arg_object):
        try:
            arg, object = arg_object
        except (TypeError, ValueError) as e:
            yield "%r: not a not data options and data dict: %s" % (arg_object, e)
        for selector, validator in self.selectors:
            if selector is None or selector(arg):
                for msg in validator.validate(name, object):
                    yield msg
                return
        yield "no match for selector argument %r" % (arg,)

# Type definitions

data = {}
message = {}
dbdict = {}

# sourcestamp

_sourcestamp = dict(
    ssid=IntValidator(),
    branch=NoneOk(StringValidator()),
    revision=NoneOk(StringValidator()),
    repository=StringValidator(),
    project=StringValidator(),
    codebase=StringValidator(),
    created_at=IntValidator(),
    patch=NoneOk(DictValidator(
        body=NoneOk(BinaryValidator()),
        level=NoneOk(IntValidator()),
        subdir=NoneOk(StringValidator()),
        author=NoneOk(StringValidator()),
        comment=NoneOk(StringValidator()))),
)
data['sourcestamp'] = Selector()
data['sourcestamp'].add(None,
    DictValidator(
        link=LinkValidator(),
        **_sourcestamp
    ))

message['sourcestamp'] = Selector()
message['sourcestamp'].add(None,
    DictValidator(
        **_sourcestamp
    ))

dbdict['ssdict'] = DictValidator(
    ssid=IntValidator(),
    branch=NoneOk(StringValidator()),
    revision=NoneOk(StringValidator()),
    patch_body=NoneOk(BinaryValidator()),
    patch_level=NoneOk(IntValidator()),
    patch_subdir=NoneOk(StringValidator()),
    patch_author=NoneOk(StringValidator()),
    patch_comment=NoneOk(StringValidator()),
    codebase=StringValidator(),
    repository=StringValidator(),
    project=StringValidator(),
    created_at=DateTimeValidator(),
)

# builder

data['builder'] = Selector()
data['builder'].add(None,
    DictValidator(
        builderid=IntValidator(),
        name=StringValidator(),
        link=LinkValidator(),
    ))

message['builder'] = Selector()
message['builder'].add(None,
    MessageValidator(
        keyFields=['builderid'],
        events=['started', 'stopped'],
        messageValidator=DictValidator(
            builderid=IntValidator(),
            masterid=IntValidator(),
            name=StringValidator(),
        )))

dbdict['builderdict'] = DictValidator(
    id=IntValidator(),
    masterids=ListValidator(IntValidator()),
    name=StringValidator(),
)

# buildset

_buildset = dict(
    bsid=IntValidator(),
    external_idstring=NoneOk(StringValidator()),
    reason=StringValidator(),
    submitted_at=IntValidator(),
    complete=BooleanValidator(),
    complete_at=NoneOk(IntValidator()),
    results=NoneOk(IntValidator()),
)
_buildsetKeyFields = ['bsid']
_buildsetEvents = ['new', 'complete']

data['buildset'] = Selector()
data['buildset'].add(None,
    DictValidator(
        sourcestamps=ListValidator(
            DictValidator(
                link=LinkValidator(),
                **_sourcestamp
            )),
        link=LinkValidator(),
        **_buildset
    ))

message['buildset'] = Selector()
message['buildset'].add(lambda k : k[-1] == 'new',
    MessageValidator(
        keyFields=_buildsetKeyFields,
        events=_buildsetEvents,
        messageValidator=DictValidator(
            scheduler=StringValidator(), # only for 'new'
            sourcestamps=ListValidator(
                DictValidator(
                    **_sourcestamp
                )),
            **_buildset
        )))
message['buildset'].add(None,
    MessageValidator(
        keyFields=_buildsetKeyFields,
        events=_buildsetEvents,
        messageValidator=DictValidator(
            sourcestamps=ListValidator(
                DictValidator(
                    **_sourcestamp
                )),
            **_buildset
        )))

dbdict['bsdict'] = DictValidator(
    bsid=IntValidator(),
    external_idstring=NoneOk(StringValidator()),
    reason=StringValidator(),
    sourcestamps=ListValidator(IntValidator()),
    submitted_at=DateTimeValidator(),
    complete=BooleanValidator(),
    complete_at=NoneOk(DateTimeValidator()),
    results=NoneOk(IntValidator()),
)

# buildrequest

message['buildrequest'] = Selector()
message['buildrequest'].add(None,
    MessageValidator(
        keyFields=['bsid', 'builderid', 'brid'],
        events=['new', 'claimed', 'unclaimed'],
        messageValidator=DictValidator(
            # TODO: probably wrong!
            brid=IntValidator(),
            builderid=IntValidator(),
            bsid=IntValidator(),
            buildername=StringValidator(),
)))

# change

data['change'] = Selector()
data['change'].add(None,
    DictValidator(
        changeid=IntValidator(),
        author=StringValidator(),
        files=ListValidator(StringValidator()),
        comments=StringValidator(),
        revision=NoneOk(StringValidator()),
        when_timestamp=IntValidator(),
        branch=NoneOk(StringValidator()),
        category=NoneOk(StringValidator()),
        revlink=NoneOk(StringValidator()),
        properties=SourcedPropertiesValidator(),
        repository=StringValidator(),
        project=StringValidator(),
        codebase=StringValidator(),
        sourcestamp=DictValidator(
            link=LinkValidator(),
            **_sourcestamp
        ),
        link=LinkValidator(),
))

message['change'] = Selector()
message['change'].add(None,
    MessageValidator(
        keyFields=['changeid'],
        events=['new'],
        messageValidator=DictValidator(
            changeid=IntValidator(),
            author=StringValidator(),
            files=ListValidator(StringValidator()),
            comments=StringValidator(),
            revision=NoneOk(StringValidator()),
            when_timestamp=IntValidator(),
            branch=NoneOk(StringValidator()),
            category=NoneOk(StringValidator()),
            revlink=NoneOk(StringValidator()),
            properties=SourcedPropertiesValidator(),
            repository=StringValidator(),
            project=StringValidator(),
            codebase=StringValidator(),
            sourcestamp=DictValidator(
                **_sourcestamp
            ),
)))

dbdict['chdict'] = DictValidator(
    changeid=IntValidator(),
    author=StringValidator(),
    files=ListValidator(StringValidator()),
    comments=StringValidator(),
    revision=NoneOk(StringValidator()),
    when_timestamp=DateTimeValidator(),
    branch=NoneOk(StringValidator()),
    category=NoneOk(StringValidator()),
    revlink=NoneOk(StringValidator()),
    properties=SourcedPropertiesValidator(),
    repository=StringValidator(),
    project=StringValidator(),
    codebase=StringValidator(),
    is_dir=IntValidator(),
    sourcestampid=IntValidator(),
)

# masters

_master = dict(
    masterid=IntValidator(),
    name=StringValidator(),
    active=BooleanValidator(),
    last_active=IntValidator(),
)
data['master'] = Selector()
data['master'].add(None,
    DictValidator(
        link=LinkValidator(),
        **_master
))

message['master'] = Selector()
message['master'].add(None,
    MessageValidator(
        keyFields=['masterid'],
        events=['started', 'stopped'],
        messageValidator=DictValidator(
            masterid=IntValidator(),
            name=StringValidator(),
            active=BooleanValidator(),
            # last_active is not included
)))

dbdict['masterdict'] = DictValidator(
    id=IntValidator(),
    name=StringValidator(),
    active=BooleanValidator(),
    last_active=DateTimeValidator(),
)

# schedulers

data['scheduler'] = Selector()
data['scheduler'].add(None,
    DictValidator(
        schedulerid=IntValidator(),
        name=StringValidator(),
        master=NoneOk(DictValidator(
            link=LinkValidator(),
            **_master)),
        link=LinkValidator(),
))

dbdict['schedulerdict'] = DictValidator(
    id=IntValidator(),
    name=StringValidator(),
    masterid=NoneOk(IntValidator()),
)

# external functions

def _verify(testcase, validator, name, object):
    msgs = list(validator.validate(name, object))
    if msgs:
        msg = "; ".join(msgs)
        if testcase:
            testcase.fail(msg)
        else:
            raise AssertionError(msg)

def verifyMessage(testcase, routingKey, message_):
    # the validator is a Selector wrapping a MessageValidator, so we need to
    # pass (arg, (routingKey, message)), where the routing key is the arg
    _verify(testcase, message[routingKey[0]], '',
            (routingKey, (routingKey, message_)))

def verifyDbDict(testcase, type, value):
    _verify(testcase, dbdict[type], type, value)

def verifyData(testcase, type, options, value):
    _verify(testcase, data[type], type, (options, value))

def verifyType(testcase, name, value, validator):
    _verify(testcase, validator, name, value)
