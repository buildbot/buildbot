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
from __future__ import annotations

import datetime
import json
import re

from buildbot.util import UTC
from buildbot.util import bytes2unicode

# Base class

validatorsByName = {}


class Validator:
    name: str | None = None
    hasArgs = False

    def validate(self, name, object):
        raise NotImplementedError

    class __metaclass__(type):
        def __new__(mcs, name, bases, attrs):
            cls = type.__new__(mcs, name, bases, attrs)
            if attrs.get('name'):
                assert attrs['name'] not in validatorsByName
                validatorsByName[attrs['name']] = cls
            return cls


# Basic types


class InstanceValidator(Validator):
    types: tuple[type] | tuple[()] = ()

    def validate(self, name, object):
        if not isinstance(object, self.types):
            yield f"{name} ({object!r}) is not a {self.name or repr(self.types)}"


class IntValidator(InstanceValidator):
    types = (int,)
    name = 'integer'


class BooleanValidator(InstanceValidator):
    types = (bool,)
    name = 'boolean'


class StringValidator(InstanceValidator):
    # strings must be unicode
    types = (str,)
    name = 'string'


class BinaryValidator(InstanceValidator):
    types = (bytes,)
    name = 'bytestring'


class StrValidator(InstanceValidator):
    types = (str,)
    name = 'str'


class DateTimeValidator(Validator):
    types = (datetime.datetime,)
    name = 'datetime'

    def validate(self, name, object):
        if not isinstance(object, datetime.datetime):
            yield f"{name} - {object!r} - is not a datetime"
        elif object.tzinfo != UTC:
            yield f"{name} is not a UTC datetime"


class IdentifierValidator(Validator):
    types = (str,)
    name = 'identifier'
    hasArgs = True

    ident_re = re.compile(
        '^[a-zA-Z\u00a0-\U0010ffff_-][a-zA-Z0-9\u00a0-\U0010ffff_-]*$', flags=re.UNICODE
    )

    def __init__(self, len):
        self.len = len

    def validate(self, name, object):
        if not isinstance(object, str):
            yield f"{name} - {object!r} - is not a unicode string"
        elif not self.ident_re.match(object):
            yield f"{name} - {object!r} - is not an identifier"
        elif not object:
            yield f"{name} - identifiers cannot be an empty string"
        elif len(object) > self.len:
            yield f"{name} - {object!r} - is longer than {self.len} characters"


# Miscellaneous


class NoneOk:
    def __init__(self, original):
        self.original = original

    def validate(self, name, object):
        if object is None:
            return
        else:
            yield from self.original.validate(name, object)


class Any:
    def validate(self, name, object):
        return


# Compound Types


class DictValidator(Validator):
    name = 'dict'

    def __init__(self, optionalNames=None, **keys):
        if optionalNames is None:
            optionalNames = []
        self.optionalNames = set(optionalNames)
        self.keys = keys
        self.expectedNames = set(keys.keys())

    def validate(self, name, object):
        # this uses isinstance, allowing dict subclasses as used by the DB API
        if not isinstance(object, dict):
            yield f"{name} ({object!r}) is not a dictionary (got type {type(object)})"
            return

        gotNames = set(object.keys())

        unexpected = gotNames - self.expectedNames
        if unexpected:
            yield f'{name} has unexpected keys {", ".join([repr(n) for n in unexpected])}'

        missing = self.expectedNames - self.optionalNames - gotNames
        if missing:
            yield f'{name} is missing keys {", ".join([repr(n) for n in missing])}'
        for k in gotNames & self.expectedNames:
            yield from self.keys[k].validate(f"{name}[{k!r}]", object[k])


class SequenceValidator(Validator):
    type: type | None = None

    def __init__(self, elementValidator):
        self.elementValidator = elementValidator

    def validate(self, name, object):
        if not isinstance(object, self.type):
            yield f"{name} ({object!r}) is not a {self.name}"
            return

        for idx, elt in enumerate(object):
            yield from self.elementValidator.validate(f"{name}[{idx}]", elt)


class ListValidator(SequenceValidator):
    type = list
    name = 'list'


class TupleValidator(SequenceValidator):
    type = tuple
    name = 'tuple'


class StringListValidator(ListValidator):
    name = 'string-list'

    def __init__(self):
        super().__init__(StringValidator())


class SourcedPropertiesValidator(Validator):
    name = 'sourced-properties'

    def validate(self, name, object):
        if not isinstance(object, dict):
            yield f"{name} is not sourced properties (not a dict)"
            return
        for k, v in object.items():
            if not isinstance(k, str):
                yield f"{name} property name {k!r} is not unicode"
            if not isinstance(v, tuple) or len(v) != 2:
                yield f"{name} property value for '{k!r}' is not a 2-tuple"
                return
            propval, propsrc = v
            if not isinstance(propsrc, str):
                yield f"{name}[{k}] source {propsrc!r} is not unicode"
            try:
                json.dumps(propval)
            except (TypeError, ValueError):
                yield f"{name}[{k!r}] value is not JSON-able"


class JsonValidator(Validator):
    name = 'json'

    def validate(self, name, object):
        try:
            json.dumps(object)
        except (TypeError, ValueError):
            yield f"{name}[{object!r}] value is not JSON-able"


class PatchValidator(Validator):
    name: str | None = 'patch'  # type: ignore[assignment]

    validator = DictValidator(
        body=NoneOk(BinaryValidator()),
        level=NoneOk(IntValidator()),
        subdir=NoneOk(StringValidator()),
        author=NoneOk(StringValidator()),
        comment=NoneOk(StringValidator()),
    )

    def validate(self, name, object):
        yield from self.validator.validate(name, object)


class MessageValidator(Validator):
    routingKeyValidator = TupleValidator(StrValidator())

    def __init__(self, events, messageValidator):
        self.events = [bytes2unicode(e) for e in set(events)]
        self.messageValidator = messageValidator

    def validate(self, name, routingKey_message):
        try:
            routingKey, message = routingKey_message
        except (TypeError, ValueError) as e:
            yield f"{routingKey_message!r}: not a routing key and message: {e}"
        routingKeyBad = False
        for msg in self.routingKeyValidator.validate("routingKey", routingKey):
            yield msg
            routingKeyBad = True

        if not routingKeyBad:
            event = routingKey[-1]
            if event not in self.events:
                yield f"routing key event {event!r} is not valid"

        yield from self.messageValidator.validate(f"{routingKey[0]} message", message)


class Selector(Validator):
    def __init__(self):
        self.selectors = []

    def add(self, selector, validator):
        self.selectors.append((selector, validator))

    def validate(self, name, arg_object):
        try:
            arg, object = arg_object
        except (TypeError, ValueError) as e:
            yield f"{arg_object!r}: not a not data options and data dict: {e}"
        for selector, validator in self.selectors:
            if selector is None or selector(arg):
                yield from validator.validate(name, object)
                return
        yield f"no match for selector argument {arg!r}"


# Type definitions

message = {}

# parse and use a ResourceType class's dataFields into a validator

# masters

message['masters'] = Selector()
message['masters'].add(
    None,
    MessageValidator(
        events=[b'started', b'stopped'],
        messageValidator=DictValidator(
            masterid=IntValidator(),
            name=StringValidator(),
            active=BooleanValidator(),
            # last_active is not included
        ),
    ),
)

# sourcestamp

_sourcestamp = {
    "ssid": IntValidator(),
    "branch": NoneOk(StringValidator()),
    "revision": NoneOk(StringValidator()),
    "repository": StringValidator(),
    "project": StringValidator(),
    "codebase": StringValidator(),
    "created_at": DateTimeValidator(),
    "patch": NoneOk(
        DictValidator(
            body=NoneOk(BinaryValidator()),
            level=NoneOk(IntValidator()),
            subdir=NoneOk(StringValidator()),
            author=NoneOk(StringValidator()),
            comment=NoneOk(StringValidator()),
        )
    ),
}

message['sourcestamps'] = Selector()
message['sourcestamps'].add(None, DictValidator(**_sourcestamp))

# builder

message['builders'] = Selector()
message['builders'].add(
    None,
    MessageValidator(
        events=[b'started', b'stopped'],
        messageValidator=DictValidator(
            builderid=IntValidator(),
            masterid=IntValidator(),
            name=StringValidator(),
        ),
    ),
)

# buildset

_buildset = {
    "bsid": IntValidator(),
    "external_idstring": NoneOk(StringValidator()),
    "reason": StringValidator(),
    "submitted_at": IntValidator(),
    "complete": BooleanValidator(),
    "complete_at": NoneOk(IntValidator()),
    "results": NoneOk(IntValidator()),
    "parent_buildid": NoneOk(IntValidator()),
    "parent_relationship": NoneOk(StringValidator()),
}
_buildsetEvents = [b'new', b'complete']

message['buildsets'] = Selector()
message['buildsets'].add(
    lambda k: k[-1] == 'new',
    MessageValidator(
        events=_buildsetEvents,
        messageValidator=DictValidator(
            scheduler=StringValidator(),  # only for 'new'
            sourcestamps=ListValidator(DictValidator(**_sourcestamp)),
            **_buildset,
        ),
    ),
)
message['buildsets'].add(
    None,
    MessageValidator(
        events=_buildsetEvents,
        messageValidator=DictValidator(
            sourcestamps=ListValidator(DictValidator(**_sourcestamp)), **_buildset
        ),
    ),
)

# buildrequest

message['buildrequests'] = Selector()
message['buildrequests'].add(
    None,
    MessageValidator(
        events=[b'new', b'claimed', b'unclaimed'],
        messageValidator=DictValidator(
            # TODO: probably wrong!
            brid=IntValidator(),
            builderid=IntValidator(),
            bsid=IntValidator(),
            buildername=StringValidator(),
        ),
    ),
)

# change

message['changes'] = Selector()
message['changes'].add(
    None,
    MessageValidator(
        events=[b'new'],
        messageValidator=DictValidator(
            changeid=IntValidator(),
            parent_changeids=ListValidator(IntValidator()),
            author=StringValidator(),
            committer=StringValidator(),
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
            sourcestamp=DictValidator(**_sourcestamp),
        ),
    ),
)

# builds

_build = {
    "buildid": IntValidator(),
    "number": IntValidator(),
    "builderid": IntValidator(),
    "buildrequestid": IntValidator(),
    "workerid": IntValidator(),
    "masterid": IntValidator(),
    "started_at": IntValidator(),
    "complete": BooleanValidator(),
    "complete_at": NoneOk(IntValidator()),
    "state_string": StringValidator(),
    "results": NoneOk(IntValidator()),
}
_buildEvents = [b'new', b'complete']

message['builds'] = Selector()
message['builds'].add(
    None, MessageValidator(events=_buildEvents, messageValidator=DictValidator(**_build))
)

# Validates DATA API layer

# build data

_build_data_msgdict = DictValidator(
    buildid=IntValidator(),
    name=StringValidator(),
    value=NoneOk(BinaryValidator()),
    length=IntValidator(),
    source=StringValidator(),
)

message['build_data'] = Selector()
message['build_data'].add(None, MessageValidator(events=[], messageValidator=_build_data_msgdict))

# steps

_step = {
    "stepid": IntValidator(),
    "number": IntValidator(),
    "name": IdentifierValidator(50),
    "buildid": IntValidator(),
    "started_at": IntValidator(),
    "complete": BooleanValidator(),
    "complete_at": NoneOk(IntValidator()),
    "state_string": StringValidator(),
    "results": NoneOk(IntValidator()),
    "urls": ListValidator(StringValidator()),
    "hidden": BooleanValidator(),
}
_stepEvents = [b'new', b'complete']

message['steps'] = Selector()
message['steps'].add(
    None, MessageValidator(events=_stepEvents, messageValidator=DictValidator(**_step))
)

# logs

_log = {
    "logid": IntValidator(),
    "name": IdentifierValidator(50),
    "stepid": IntValidator(),
    "complete": BooleanValidator(),
    "num_lines": IntValidator(),
    "type": IdentifierValidator(1),
}
_logEvents = ['new', 'complete', 'appended']

# test results sets

_test_result_set_msgdict = DictValidator(
    builderid=IntValidator(),
    buildid=IntValidator(),
    stepid=IntValidator(),
    description=NoneOk(StringValidator()),
    category=StringValidator(),
    value_unit=StringValidator(),
    tests_passed=NoneOk(IntValidator()),
    tests_failed=NoneOk(IntValidator()),
    complete=BooleanValidator(),
)

message['test_result_sets'] = Selector()
message['test_result_sets'].add(
    None, MessageValidator(events=[b'new', b'completed'], messageValidator=_test_result_set_msgdict)
)

# test results

_test_results_msgdict = DictValidator(
    builderid=IntValidator(),
    test_result_setid=IntValidator(),
    test_name=NoneOk(StringValidator()),
    test_code_path=NoneOk(StringValidator()),
    line=NoneOk(IntValidator()),
    duration_ns=NoneOk(IntValidator()),
    value=StringValidator(),
)

message['test_results'] = Selector()
message['test_results'].add(
    None, MessageValidator(events=[b'new'], messageValidator=_test_results_msgdict)
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
    # the "type" of the message is identified by last path name
    # -1 being the event, and -2 the id.

    validator = message[bytes2unicode(routingKey[-3])]
    _verify(testcase, validator, '', (routingKey, (routingKey, message_)))


def verifyData(testcase, entityType, options, value):
    _verify(testcase, entityType, entityType.name, value)


def verifyType(testcase, name, value, validator):
    _verify(testcase, validator, name, value)
