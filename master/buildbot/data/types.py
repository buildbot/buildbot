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
import datetime
import json
import re

from buildbot import util
from buildbot.util import bytes2unicode


class Type:

    name = None
    doc = None

    @property
    def ramlname(self):
        return self.name

    def valueFromString(self, arg):
        # convert a urldecoded bytestring as given in a URL to a value, or
        # raise an exception trying.  This parent method raises an exception,
        # so if the method is missing in a subclass, it cannot be created from
        # a string.
        raise TypeError

    def cmp(self, val, arg):
        argVal = self.valueFromString(arg)
        if val < argVal:
            return -1
        elif val == argVal:
            return 0
        return 1

    def validate(self, name, object):
        raise NotImplementedError

    def getSpec(self):
        r = dict(name=self.name)
        if self.doc is not None:
            r["doc"] = self.doc
        return r


class NoneOk(Type):

    def __init__(self, nestedType):
        assert isinstance(nestedType, Type)
        self.nestedType = nestedType
        self.name = self.nestedType.name + " or None"

    @property
    def ramlname(self):
        return self.nestedType.ramlname

    def valueFromString(self, arg):
        return self.nestedType.valueFromString(arg)

    def cmp(self, val, arg):
        return self.nestedType.cmp(val, arg)

    def validate(self, name, object):
        if object is None:
            return
        for msg in self.nestedType.validate(name, object):
            yield msg

    def getSpec(self):
        r = self.nestedType.getSpec()
        r["can_be_null"] = True
        return r

    def toRaml(self):
        return self.nestedType.toRaml()


class Instance(Type):

    types = ()
    ramlType = "unknown"

    @property
    def ramlname(self):
        return self.ramlType

    def validate(self, name, object):
        if not isinstance(object, self.types):
            yield "{} ({}) is not a {}".format(name, repr(object), self.name or repr(self.types))

    def toRaml(self):
        return self.ramlType


class Integer(Instance):

    name = "integer"
    types = (int,)
    ramlType = "integer"

    def valueFromString(self, arg):
        return int(arg)


class DateTime(Instance):
    name = "datetime"
    types = (datetime.datetime)
    ramlType = "date"


class String(Instance):

    name = "string"
    types = (str,)
    ramlType = "string"

    def valueFromString(self, arg):
        val = util.bytes2unicode(arg)
        return val


class Binary(Instance):

    name = "binary"
    types = (bytes,)
    ramlType = "string"

    def valueFromString(self, arg):
        return arg


class Boolean(Instance):

    name = "boolean"
    types = (bool,)
    ramlType = "boolean"

    def valueFromString(self, arg):
        return util.string2boolean(arg)


class Identifier(Type):

    name = "identifier"
    identRe = re.compile('^[a-zA-Z_-][a-zA-Z0-9._-]*$')
    ramlType = "string"

    def __init__(self, len=None, **kwargs):
        super().__init__(**kwargs)
        self.len = len

    def valueFromString(self, arg):
        val = util.bytes2unicode(arg)
        if not self.identRe.match(val) or len(val) > self.len or not val:
            raise TypeError
        return val

    def validate(self, name, object):
        if not isinstance(object, str):
            yield "{} - {} - is not a unicode string".format(name, repr(object))
        elif not self.identRe.match(object):
            yield "{} - {} - is not an identifier".format(name, repr(object))
        elif not object:
            yield "{} - identifiers cannot be an empty string".format(name)
        elif len(object) > self.len:
            yield "{} - {} - is longer than {} characters".format(name, repr(object), self.len)

    def toRaml(self):
        return {'type': self.ramlType,
                'pattern': self.identRe.pattern}


class List(Type):

    name = "list"
    ramlType = "list"

    @property
    def ramlname(self):
        return self.of.ramlname

    def __init__(self, of=None, **kwargs):
        super().__init__(**kwargs)
        self.of = of

    def validate(self, name, object):
        if not isinstance(object, list):  # we want a list, and NOT a subclass
            yield "{} ({}) is not a {}".format(name, repr(object), self.name)
            return

        for idx, elt in enumerate(object):
            for msg in self.of.validate("{}[{}]".format(name, idx), elt):
                yield msg

    def valueFromString(self, arg):
        # valueFromString is used to process URL args, which come one at
        # a time, so we defer to the `of`
        return self.of.valueFromString(arg)

    def getSpec(self):
        return dict(type=self.name,
                    of=self.of.getSpec())

    def toRaml(self):
        return {'type': 'array', 'items': self.of.name}


def maybeNoneOrList(k, v):
    if isinstance(v, NoneOk):
        return k + "?"
    if isinstance(v, List):
        return k + "[]"
    return k


class SourcedProperties(Type):

    name = "sourcedproperties"

    def validate(self, name, object):
        if not isinstance(object, dict):  # we want a dict, and NOT a subclass
            yield "{} is not sourced properties (not a dict)".format(name)
            return
        for k, v in object.items():
            if not isinstance(k, str):
                yield "{} property name {} is not unicode".format(name, repr(k))
            if not isinstance(v, tuple) or len(v) != 2:
                yield "{} property value for '{}' is not a 2-tuple".format(name, k)
                return
            propval, propsrc = v
            if not isinstance(propsrc, str):
                yield "{}[{}] source {} is not unicode".format(name, k, repr(propsrc))
            try:
                json.loads(bytes2unicode(propval))
            except ValueError:
                yield "{}[{}] value is not JSON-able".format(name, repr(k))

    def toRaml(self):
        return {'type': "object",
                'properties':
                {'[]': {'type': 'object',
                        'properties': {
                            1: 'string',
                            2: 'integer | string | object | array | boolean'
                        }
                        }}}


class Dict(Type):
    name = "dict"

    @property
    def ramlname(self):
        return self.toRaml()

    def __init__(self, **contents):
        self.contents = contents
        self.keys = set(contents)

    def validate(self, name, object):
        if not isinstance(object, dict):
            yield "{} ({}) is not a dictionary (got type {})".format(name, repr(object),
                                                                     type(object))
            return

        gotNames = set(object.keys())

        unexpected = gotNames - self.keys
        if unexpected:
            yield "{} has unexpected keys {}".format(name, ", ".join([repr(n) for n in unexpected]))

        missing = self.keys - gotNames
        if missing:
            yield "{} is missing keys {}".format(name, ", ".join([repr(n) for n in missing]))

        for k in gotNames & self.keys:
            f = self.contents[k]
            for msg in f.validate("{}[{}]".format(name, repr(k)), object[k]):
                yield msg

    def getSpec(self):
        return dict(type=self.name,
                    fields=[dict(name=k,
                                 type=v.name,
                                 type_spec=v.getSpec())
                            for k, v in self.contents.items()
                            ])

    def toRaml(self):
        return {'type': "object",
                'properties': {maybeNoneOrList(k, v): v.ramlname for k, v in self.contents.items()}}


class JsonObject(Type):
    name = "jsonobject"
    ramlname = 'object'

    def validate(self, name, object):
        if not isinstance(object, dict):
            yield "{} ({}) is not a dictionary (got type {})".format(name, repr(object),
                                                                     type(object))
            return

        # make sure JSON can represent it
        try:
            json.dumps(object)
        except Exception as e:
            yield "{} is not JSON-able: {}".format(name, e)
            return

    def toRaml(self):
        return "object"


class Entity(Type):

    # NOTE: this type is defined by subclassing it in each resource type class.
    # Instances are generally accessed at e.g.,
    #  * buildsets.Buildset.entityType or
    #  * self.master.data.rtypes.buildsets.entityType

    name = None  # set in constructor
    fields = {}
    fieldNames = set([])

    def __init__(self, name):
        fields = {}
        for k, v in self.__class__.__dict__.items():
            if isinstance(v, Type):
                fields[k] = v
        self.fields = fields
        self.fieldNames = set(fields)
        self.name = name

    def validate(self, name, object):
        # this uses isinstance, allowing dict subclasses as used by the DB API
        if not isinstance(object, dict):
            yield "{} ({}) is not a dictionary (got type {})".format(name, repr(object),
                                                                     type(object))
            return

        gotNames = set(object.keys())

        unexpected = gotNames - self.fieldNames
        if unexpected:
            yield "{} has unexpected keys {}".format(name, ", ".join([repr(n) for n in unexpected]))

        missing = self.fieldNames - gotNames
        if missing:
            yield "{} is missing keys {}".format(name, ", ".join([repr(n) for n in missing]))

        for k in gotNames & self.fieldNames:
            f = self.fields[k]
            for msg in f.validate("{}[{}]".format(name, repr(k)), object[k]):
                yield msg

    def getSpec(self):
        return dict(type=self.name,
                    fields=[dict(name=k,
                                 type=v.name,
                                 type_spec=v.getSpec())
                            for k, v in self.fields.items()
                            ])

    def toRaml(self):
        return {'type': "object",
                'properties': {
                    maybeNoneOrList(k, v): {'type': v.ramlname, 'description': ''}
                    for k, v in self.fields.items()}}
