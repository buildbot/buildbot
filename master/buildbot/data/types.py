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
from typing import TYPE_CHECKING
from typing import Any

from buildbot import util
from buildbot.util import bytes2unicode

if TYPE_CHECKING:
    from collections.abc import Generator


def capitalize(word: str) -> str:
    return ''.join(x.capitalize() or '_' for x in word.split('_'))


class Type:
    name: Identifier | String | str | None = None
    doc: str | None = None
    graphQLType = "unknown"

    @property
    def ramlname(self) -> Identifier | String | str | None:
        return self.name

    def valueFromString(self, arg: Any) -> Any:
        # convert a urldecoded bytestring as given in a URL to a value, or
        # raise an exception trying.  This parent method raises an exception,
        # so if the method is missing in a subclass, it cannot be created from
        # a string.
        raise TypeError

    def cmp(self, val: Any, arg: Any) -> int:
        argVal = self.valueFromString(arg)
        if val < argVal:
            return -1
        elif val == argVal:
            return 0
        return 1

    def validate(self, name: str, object: Any) -> Generator[str, None, None]:
        raise NotImplementedError

    def getSpec(self) -> dict[str, Any]:
        r: dict[str, Any] = {"name": self.name}
        if self.doc is not None:
            r["doc"] = self.doc
        return r

    def toGraphQL(self) -> str:
        return self.graphQLType

    def toGraphQLTypeName(self) -> str:
        return self.graphQLType

    def graphQLDependentTypes(self) -> list[Type]:
        return []

    def getGraphQLInputType(self) -> str | None:
        return self.toGraphQLTypeName()

    def toRaml(self) -> Any:
        raise NotImplementedError


class NoneOk(Type):
    def __init__(self, nestedType: Type) -> None:
        assert isinstance(nestedType, Type)
        self.nestedType = nestedType
        self.name = str(self.nestedType.name) + " or None"

    @property
    def ramlname(self) -> Identifier | String | str | None:
        return self.nestedType.ramlname

    def valueFromString(self, arg: Any) -> Any:
        return self.nestedType.valueFromString(arg)

    def cmp(self, val: Any, arg: Any) -> int:
        return self.nestedType.cmp(val, arg)

    def validate(self, name: str, object: Any) -> Generator[str, None, None]:
        if object is None:
            return
        yield from self.nestedType.validate(name, object)

    def getSpec(self) -> dict[str, Any]:
        r = self.nestedType.getSpec()
        r["can_be_null"] = True
        return r

    def toRaml(self) -> Any:
        return self.nestedType.toRaml()


class Instance(Type):
    types: tuple[type, ...] = ()
    ramlType = "unknown"
    graphQLType = "unknown"

    @property
    def ramlname(self) -> str:
        return self.ramlType

    def validate(self, name: str, object: Any) -> Generator[str, None, None]:
        if not isinstance(object, self.types):
            yield f"{name} ({object!r}) is not a {self.name or repr(self.types)}"

    def toRaml(self) -> str:
        return self.ramlType

    def toGraphQL(self) -> str:
        return self.graphQLType + "!"


class Integer(Instance):
    name = "integer"
    types = (int,)
    ramlType = "integer"
    graphQLType = "Int"

    def valueFromString(self, arg: Any) -> int:
        return int(arg)


class DateTime(Instance):
    name = "datetime"
    types = (datetime.datetime,)
    ramlType = "date"
    graphQLType = "Date"  # custom

    def valueFromString(self, arg: Any) -> int:
        return int(arg)

    def validate(self, name: str, object: Any) -> Generator[str, None, None]:
        if isinstance(object, datetime.datetime):
            return
        if isinstance(object, int):
            try:
                datetime.datetime.fromtimestamp(object)
            except (OverflowError, OSError):
                pass
            else:
                return
        yield f"{name} ({object}) is not a valid timestamp"


class String(Instance):
    name = "string"
    types = (str,)
    ramlType = "string"
    graphQLType = "String"

    def valueFromString(self, arg: Any) -> str:
        val = util.bytes2unicode(arg)
        return val


class Binary(Instance):
    name = "binary"
    types = (bytes,)
    ramlType = "string"
    graphQLType = "Binary"  # custom

    def valueFromString(self, arg: Any) -> Any:
        return arg


class Boolean(Instance):
    name = "boolean"
    types = (bool,)
    ramlType = "boolean"
    graphQLType = "Boolean"  # custom

    def valueFromString(self, arg: Any) -> bool:
        return util.string2boolean(arg)


class Identifier(Type):
    name = "identifier"
    identRe = re.compile('^[a-zA-Z_-][a-zA-Z0-9._-]*$')
    ramlType = "string"
    graphQLType = "String"

    def __init__(self, len: int | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.len = len

    def valueFromString(self, arg: Any) -> str:
        val = util.bytes2unicode(arg)
        if not self.identRe.match(val) or len(val) > self.len or not val:  # type: ignore[operator]
            raise TypeError
        return val

    def validate(self, name: str, object: Any) -> Generator[str, None, None]:
        if not isinstance(object, str):
            yield f"{name} - {object!r} - is not a unicode string"
        elif not self.identRe.match(object):
            yield f"{name} - {object!r} - is not an identifier"
        elif not object:
            yield f"{name} - identifiers cannot be an empty string"
        elif len(object) > self.len:  # type: ignore[operator]
            yield f"{name} - {object!r} - is longer than {self.len} characters"

    def toRaml(self) -> dict[str, str]:
        return {'type': self.ramlType, 'pattern': self.identRe.pattern}


class List(Type):
    name = "list"
    ramlType = "list"

    @property
    def ramlname(self) -> Identifier | String | str | None:
        return self.of.ramlname  # type: ignore[union-attr]

    def __init__(self, of: Type | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.of = of

    def validate(self, name: str, object: Any) -> Generator[str, None, None]:
        if not isinstance(object, list):  # we want a list, and NOT a subclass
            yield f"{name} ({object!r}) is not a {self.name}"
            return

        for idx, elt in enumerate(object):
            yield from self.of.validate(f"{name}[{idx}]", elt)  # type: ignore[union-attr]

    def valueFromString(self, arg: Any) -> Any:
        # valueFromString is used to process URL args, which come one at
        # a time, so we defer to the `of`
        return self.of.valueFromString(arg)  # type: ignore[union-attr]

    def getSpec(self) -> dict[str, Any]:
        return {"type": self.name, "of": self.of.getSpec()}  # type: ignore[union-attr]

    def toRaml(self) -> dict[str, Any]:
        return {'type': 'array', 'items': self.of.name}  # type: ignore[union-attr]

    def toGraphQL(self) -> str:
        return f"[{self.of.toGraphQLTypeName()}]!"  # type: ignore[union-attr]

    def toGraphQLTypeName(self) -> str:
        return f"[{self.of.toGraphQLTypeName()}]"  # type: ignore[union-attr]

    def graphQLDependentTypes(self) -> list[Type]:
        return [self.of]  # type: ignore[list-item]

    def getGraphQLInputType(self) -> str | None:
        return self.of.getGraphQLInputType()  # type: ignore[union-attr]


def ramlMaybeNoneOrList(k: str, v: Type) -> str:
    if isinstance(v, NoneOk):
        return k + "?"
    if isinstance(v, List):
        return k + "[]"
    return k


class SourcedProperties(Type):
    name = "sourcedproperties"

    def validate(self, name: str, object: Any) -> Generator[str, None, None]:
        if not isinstance(object, dict):  # we want a dict, and NOT a subclass
            yield f"{name} is not sourced properties (not a dict)"
            return
        for k, v in object.items():
            if not isinstance(k, str):
                yield f"{name} property name {k!r} is not unicode"
            if not isinstance(v, tuple) or len(v) != 2:
                yield f"{name} property value for '{k}' is not a 2-tuple"
                return
            propval, propsrc = v
            if not isinstance(propsrc, str):
                yield f"{name}[{k}] source {propsrc!r} is not unicode"
            try:
                json.loads(bytes2unicode(propval))  # type: ignore[arg-type]
            except ValueError:
                yield f"{name}[{k!r}] value is not JSON-able"

    def toRaml(self) -> dict[str, Any]:
        return {
            'type': "object",
            'properties': {
                '[]': {
                    'type': 'object',
                    'properties': {1: 'string', 2: 'integer | string | object | array | boolean'},
                }
            },
        }

    def toGraphQL(self) -> str:
        return "[Property]!"

    def graphQLDependentTypes(self) -> list[Type]:
        return [PropertyEntityType("property", 'Property')]  # type: ignore[call-arg]

    def getGraphQLInputType(self) -> None:
        return None


class JsonObject(Type):
    name = "jsonobject"
    ramlname = 'object'
    graphQLType = "JSON"

    def validate(self, name: str, object: Any) -> Generator[str, None, None]:
        if not isinstance(object, dict):
            yield f"{name} ({object!r}) is not a dictionary (got type {type(object)})"
            return

        # make sure JSON can represent it
        try:
            json.dumps(object)
        except Exception as e:
            yield f"{name} is not JSON-able: {e}"
            return

    def toRaml(self) -> str:
        return "object"


class Entity(Type):
    # NOTE: this type is defined by subclassing it in each resource type class.
    # Instances are generally accessed at e.g.,
    #  * buildsets.Buildset.entityType or
    #  * self.master.data.rtypes.buildsets.entityType

    name: Identifier | String | str | None = None  # set in constructor
    fields: dict[str, Type] = {}
    fieldNames: set[str] = set([])

    def __init__(self, name: Identifier | String | str) -> None:
        fields = {}
        for k, v in self.__class__.__dict__.items():
            if isinstance(v, Type):
                fields[k] = v
        self.fields = fields
        self.fieldNames = set(fields)
        self.name = name

    def validate(self, name: str, object: Any) -> Generator[str, None, None]:
        # this uses isinstance, allowing dict subclasses as used by the DB API
        if not isinstance(object, dict):
            yield f"{name} ({object!r}) is not a dictionary (got type {type(object)})"
            return

        gotNames = set(object.keys())

        unexpected = gotNames - self.fieldNames
        if unexpected:
            yield f'{name} has unexpected keys {", ".join([repr(n) for n in unexpected])}'

        missing = self.fieldNames - gotNames
        if missing:
            yield f'{name} is missing keys {", ".join([repr(n) for n in missing])}'

        for k in gotNames & self.fieldNames:
            f = self.fields[k]
            yield from f.validate(f"{name}[{k!r}]", object[k])

    def getSpec(self) -> dict[str, Any]:
        return {
            "type": self.name,
            "fields": [
                {"name": k, "type": v.name, "type_spec": v.getSpec()}
                for k, v in self.fields.items()
            ],
        }

    def toRaml(self) -> dict[str, Any]:
        return {
            'type': "object",
            'properties': {
                ramlMaybeNoneOrList(k, v): {'type': v.ramlname, 'description': ''}
                for k, v in self.fields.items()
            },
        }


class PropertyEntityType(Entity):
    name = String()
    source = String()
    value = JsonObject()
