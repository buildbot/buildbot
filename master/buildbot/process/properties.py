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

import collections
import json
import re
import weakref

from twisted.internet import defer
from twisted.python.components import registerAdapter
from zope.interface import implementer

from buildbot import config
from buildbot import util
from buildbot.interfaces import IProperties
from buildbot.interfaces import IRenderable
from buildbot.util import flatten


@implementer(IProperties)
class Properties(util.ComparableMixin):

    """
    I represent a set of properties that can be interpolated into various
    strings in buildsteps.

    @ivar properties: dictionary mapping property values to tuples
        (value, source), where source is a string identifying the source
        of the property.

    Objects of this class can be read like a dictionary -- in this case,
    only the property value is returned.

    As a special case, a property value of None is returned as an empty
    string when used as a mapping.
    """

    compare_attrs = ('properties',)

    def __init__(self, **kwargs):
        """
        @param kwargs: initial property values (for testing)
        """
        self.properties = {}
        # Track keys which are 'runtime', and should not be
        # persisted if a build is rebuilt
        self.runtime = set()
        self.build = None  # will be set by the Build when starting
        self._used_secrets = {}
        if kwargs:
            self.update(kwargs, "TEST")
        self._master = None
        self._sourcestamps = None
        self._changes = None

    @property
    def master(self):
        if self.build is not None:
            return self.build.master
        return self._master

    @master.setter
    def master(self, value):
        self._master = value

    @property
    def sourcestamps(self):
        if self.build is not None:
            return [b.asDict() for b in self.build.getAllSourceStamps()]
        elif self._sourcestamps is not None:
            return self._sourcestamps
        raise AttributeError('neither build nor _sourcestamps are set')

    @sourcestamps.setter
    def sourcestamps(self, value):
        self._sourcestamps = value

    def getSourceStamp(self, codebase=''):
        for source in self.sourcestamps:
            if source['codebase'] == codebase:
                return source
        return None

    @property
    def changes(self):
        if self.build is not None:
            return [c.asChDict() for c in self.build.allChanges()]
        elif self._changes is not None:
            return self._changes
        raise AttributeError('neither build nor _changes are set')

    @changes.setter
    def changes(self, value):
        self._changes = value

    @property
    def files(self):
        if self.build is not None:
            return self.build.allFiles()
        files = []
        # self.changes, not self._changes to raise AttributeError if unset
        for chdict in self.changes:
            files.extend(chdict['files'])
        return files

    @classmethod
    def fromDict(cls, propDict):
        properties = cls()
        for name, (value, source) in propDict.items():
            properties.setProperty(name, value, source)
        return properties

    def __getstate__(self):
        d = self.__dict__.copy()
        d['build'] = None
        return d

    def __setstate__(self, d):
        self.__dict__ = d
        if not hasattr(self, 'runtime'):
            self.runtime = set()

    def __contains__(self, name):
        return name in self.properties

    def __getitem__(self, name):
        """Just get the value for this property."""
        rv = self.properties[name][0]
        return rv

    def __bool__(self):
        return bool(self.properties)

    def getPropertySource(self, name):
        return self.properties[name][1]

    def asList(self):
        """Return the properties as a sorted list of (name, value, source)"""
        ret = sorted([(k, v[0], v[1]) for k, v in self.properties.items()])
        return ret

    def asDict(self):
        """Return the properties as a simple key:value dictionary,
        properly unicoded"""
        return self.properties.copy()

    def __repr__(self):
        return ('Properties(**' +
                repr(dict((k, v[0]) for k, v in self.properties.items())) +
                ')')

    def update(self, dict, source, runtime=False):
        """Update this object from a dictionary, with an explicit source specified."""
        for k, v in dict.items():
            self.setProperty(k, v, source, runtime=runtime)

    def updateFromProperties(self, other):
        """Update this object based on another object; the other object's """
        self.properties.update(other.properties)
        self.runtime.update(other.runtime)

    def updateFromPropertiesNoRuntime(self, other):
        """Update this object based on another object, but don't
        include properties that were marked as runtime."""
        for k, v in other.properties.items():
            if k not in other.runtime:
                self.properties[k] = v

    # IProperties methods

    def getProperty(self, name, default=None):
        return self.properties.get(name, (default,))[0]

    def hasProperty(self, name):
        return name in self.properties

    has_key = hasProperty

    def setProperty(self, name, value, source, runtime=False):
        name = util.bytes2unicode(name)
        if not IRenderable.providedBy(value):
            json.dumps(value)  # Let the exception propagate ...
        source = util.bytes2unicode(source)

        self.properties[name] = (value, source)
        if runtime:
            self.runtime.add(name)

    def getProperties(self):
        return self

    def getBuild(self):
        return self.build

    def render(self, value):
        renderable = IRenderable(value)
        return defer.maybeDeferred(renderable.getRenderingFor, self)

    # as the secrets are used in the renderable, they can pretty much arrive anywhere
    # in the log of state strings
    # so we have the renderable record here which secrets are used that we must remove
    def useSecret(self, secret_value, secret_name):
        if secret_value.strip():
            self._used_secrets[secret_value] = "<" + secret_name + ">"

    # This method shall then be called to remove secrets from any text that could be logged
    # somewhere and that could contain secrets
    def cleanupTextFromSecrets(self, text):
        # Better be correct and inefficient than efficient and wrong
        secrets = self._used_secrets
        for k in sorted(secrets, key=len, reverse=True):
            text = text.replace(k, secrets[k])
        return text


class PropertiesMixin:

    """
    A mixin to add L{IProperties} methods to a class which does not implement
    the full interface, only getProperties() function.

    This is useful because L{IProperties} methods are often called on L{Build}
    objects without first coercing them.

    @ivar set_runtime_properties: the default value for the C{runtime}
    parameter of L{setProperty}.
    """

    set_runtime_properties = False

    def getProperty(self, propname, default=None):
        return self.getProperties().getProperty(propname, default)

    def hasProperty(self, propname):
        return self.getProperties().hasProperty(propname)

    has_key = hasProperty

    def setProperty(self, propname, value, source='Unknown', runtime=None):
        # source is not optional in IProperties, but is optional here to avoid
        # breaking user-supplied code that fails to specify a source
        props = self.getProperties()
        if runtime is None:
            runtime = self.set_runtime_properties
        props.setProperty(propname, value, source, runtime=runtime)

    def render(self, value):
        return self.getProperties().render(value)


@implementer(IRenderable)
class RenderableOperatorsMixin:

    """
    Properties and Interpolate instances can be manipulated with standard operators.
    """

    def __eq__(self, other):
        return _OperatorRenderer(self, other, "==", lambda v1, v2: v1 == v2)

    def __ne__(self, other):
        return _OperatorRenderer(self, other, "!=", lambda v1, v2: v1 != v2)

    def __lt__(self, other):
        return _OperatorRenderer(self, other, "<", lambda v1, v2: v1 < v2)

    def __le__(self, other):
        return _OperatorRenderer(self, other, "<=", lambda v1, v2: v1 <= v2)

    def __gt__(self, other):
        return _OperatorRenderer(self, other, ">", lambda v1, v2: v1 > v2)

    def __ge__(self, other):
        return _OperatorRenderer(self, other, ">=", lambda v1, v2: v1 >= v2)

    def __add__(self, other):
        return _OperatorRenderer(self, other, "+", lambda v1, v2: v1 + v2)

    def __sub__(self, other):
        return _OperatorRenderer(self, other, "-", lambda v1, v2: v1 - v2)

    def __mul__(self, other):
        return _OperatorRenderer(self, other, "*", lambda v1, v2: v1 * v2)

    def __truediv__(self, other):
        return _OperatorRenderer(self, other, "/", lambda v1, v2: v1 / v2)

    def __floordiv__(self, other):
        return _OperatorRenderer(self, other, "//", lambda v1, v2: v1 // v2)

    def __mod__(self, other):
        return _OperatorRenderer(self, other, "%", lambda v1, v2: v1 % v2)

    # we cannot use this trick to overload the 'in' operator, as python will force the result
    # of __contains__ to a boolean, forcing it to True all the time
    # so we mimic sqlalchemy and make a in_ method
    def in_(self, other):
        return _OperatorRenderer(self, other, "in", lambda v1, v2: v1 in v2)


@implementer(IRenderable)
class _OperatorRenderer(RenderableOperatorsMixin, util.ComparableMixin):
    """
    An instance of this class renders a comparison given by a operator
    function with v1 and v2

    """

    compare_attrs = ('fn',)

    def __init__(self, v1, v2, cstr, comparator):
        self.v1, self.v2, self.comparator, self.cstr = v1, v2, comparator, cstr

    @defer.inlineCallbacks
    def getRenderingFor(self, props):
        v1, v2 = yield props.render((self.v1, self.v2))
        return self.comparator(v1, v2)

    def __repr__(self):
        return f'{repr(self.v1)} {str(self.cstr)} {repr(self.v2)}'


class _PropertyMap:

    """
    Privately-used mapping object to implement WithProperties' substitutions,
    including the rendering of None as ''.
    """
    colon_minus_re = re.compile(r"(.*):-(.*)")
    colon_tilde_re = re.compile(r"(.*):~(.*)")
    colon_plus_re = re.compile(r"(.*):\+(.*)")

    def __init__(self, properties):
        # use weakref here to avoid a reference loop
        self.properties = weakref.ref(properties)
        self.temp_vals = {}

    def __getitem__(self, key):
        properties = self.properties()
        assert properties is not None

        def colon_minus(mo):
            # %(prop:-repl)s
            # if prop exists, use it; otherwise, use repl
            prop, repl = mo.group(1, 2)
            if prop in self.temp_vals:
                return self.temp_vals[prop]
            elif prop in properties:
                return properties[prop]
            return repl

        def colon_tilde(mo):
            # %(prop:~repl)s
            # if prop exists and is true (nonempty), use it; otherwise, use
            # repl
            prop, repl = mo.group(1, 2)
            if prop in self.temp_vals and self.temp_vals[prop]:
                return self.temp_vals[prop]
            elif prop in properties and properties[prop]:
                return properties[prop]
            return repl

        def colon_plus(mo):
            # %(prop:+repl)s
            # if prop exists, use repl; otherwise, an empty string
            prop, repl = mo.group(1, 2)
            if prop in properties or prop in self.temp_vals:
                return repl
            return ''

        for regexp, fn in [
            (self.colon_minus_re, colon_minus),
            (self.colon_tilde_re, colon_tilde),
            (self.colon_plus_re, colon_plus),
        ]:
            mo = regexp.match(key)
            if mo:
                rv = fn(mo)
                break
        else:
            # If explicitly passed as a kwarg, use that,
            # otherwise, use the property value.
            if key in self.temp_vals:
                rv = self.temp_vals[key]
            else:
                rv = properties[key]

        # translate 'None' to an empty string
        if rv is None:
            rv = ''
        return rv

    def add_temporary_value(self, key, val):
        'Add a temporary value (to support keyword arguments to WithProperties)'
        self.temp_vals[key] = val


@implementer(IRenderable)
class WithProperties(util.ComparableMixin):

    """
    This is a marker class, used fairly widely to indicate that we
    want to interpolate build properties.
    """

    compare_attrs = ('fmtstring', 'args', 'lambda_subs')

    def __init__(self, fmtstring, *args, **lambda_subs):
        self.fmtstring = fmtstring
        self.args = args
        if not self.args:
            self.lambda_subs = lambda_subs
            for key, val in self.lambda_subs.items():
                if not callable(val):
                    raise ValueError(f'Value for lambda substitution "{key}" must be callable.')
        elif lambda_subs:
            raise ValueError(
                'WithProperties takes either positional or keyword substitutions, not both.')

    def getRenderingFor(self, build):
        pmap = _PropertyMap(build.getProperties())
        if self.args:
            strings = []
            for name in self.args:
                strings.append(pmap[name])
            s = self.fmtstring % tuple(strings)
        else:
            for k, v in self.lambda_subs.items():
                pmap.add_temporary_value(k, v(build))
            s = self.fmtstring % pmap
        return s


class _NotHasKey(util.ComparableMixin):

    """A marker for missing ``hasKey`` parameter.

    To withstand ``deepcopy``, ``reload`` and pickle serialization round trips,
    check it with ``==`` or ``!=``.
    """
    compare_attrs = ()


# any instance of _NotHasKey would do, yet we don't want to create and delete
# them all the time
_notHasKey = _NotHasKey()


@implementer(IRenderable)
class _Lookup(util.ComparableMixin):

    compare_attrs = (
        'value', 'index', 'default', 'defaultWhenFalse', 'hasKey', 'elideNoneAs')

    def __init__(self, value, index, default=None,
                 defaultWhenFalse=True, hasKey=_notHasKey,
                 elideNoneAs=None):
        self.value = value
        self.index = index
        self.default = default
        self.defaultWhenFalse = defaultWhenFalse
        self.hasKey = hasKey
        self.elideNoneAs = elideNoneAs

    def __repr__(self):
        parts = [repr(self.index)]
        if self.default is not None:
            parts.append(f', default={repr(self.default)}')
        if not self.defaultWhenFalse:
            parts.append(', defaultWhenFalse=False')
        if self.hasKey != _notHasKey:
            parts.append(f', hasKey={repr(self.hasKey)}')
        if self.elideNoneAs is not None:
            parts.append(f', elideNoneAs={repr(self.elideNoneAs)}')

        parts_str = ''.join(parts)

        return f'_Lookup({repr(self.value)}, {parts_str})'

    @defer.inlineCallbacks
    def getRenderingFor(self, build):
        value = build.render(self.value)
        index = build.render(self.index)
        value, index = yield defer.gatherResults([value, index])
        if index not in value:
            rv = yield build.render(self.default)
        else:
            if self.defaultWhenFalse:
                rv = yield build.render(value[index])
                if not rv:
                    rv = yield build.render(self.default)
                elif self.hasKey != _notHasKey:
                    rv = yield build.render(self.hasKey)
            elif self.hasKey != _notHasKey:
                rv = yield build.render(self.hasKey)
            else:
                rv = yield build.render(value[index])
        if rv is None:
            rv = yield build.render(self.elideNoneAs)
        return rv


def _getInterpolationList(fmtstring):
    # TODO: Verify that no positional substitutions are requested
    dd = collections.defaultdict(str)
    fmtstring % dd
    return list(dd)


@implementer(IRenderable)
class _PropertyDict:

    def getRenderingFor(self, build):
        return build.getProperties()


_thePropertyDict = _PropertyDict()


@implementer(IRenderable)
class _WorkerPropertyDict:

    def getRenderingFor(self, build):
        return build.getBuild().getWorkerInfo()


_theWorkerPropertyDict = _WorkerPropertyDict()


@implementer(IRenderable)
class _SecretRenderer:

    def __init__(self, secret_name):
        self.secret_name = secret_name

    @defer.inlineCallbacks
    def getRenderingFor(self, properties):
        secretsSrv = properties.master.namedServices.get("secrets")
        if not secretsSrv:
            error_message = "secrets service not started, need to configure" \
                            " SecretManager in c['services'] to use 'secrets'" \
                            "in Interpolate"
            raise KeyError(error_message)
        credsservice = properties.master.namedServices['secrets']
        secret_detail = yield credsservice.get(self.secret_name)
        if secret_detail is None:
            raise KeyError(f"secret key {self.secret_name} is not found in any provider")
        properties.useSecret(secret_detail.value, self.secret_name)
        return secret_detail.value


class Secret(_SecretRenderer):

    def __repr__(self):
        return f"Secret({self.secret_name})"


class _SecretIndexer:

    def __contains__(self, password):
        return True

    def __getitem__(self, password):
        return _SecretRenderer(password)


@implementer(IRenderable)
class _SourceStampDict(util.ComparableMixin):

    compare_attrs = ('codebase',)

    def __init__(self, codebase):
        self.codebase = codebase

    def getRenderingFor(self, props):
        ss = props.getSourceStamp(self.codebase)
        if ss:
            return ss
        return {}


@implementer(IRenderable)
class _Lazy(util.ComparableMixin):

    compare_attrs = ('value',)

    def __init__(self, value):
        self.value = value

    def getRenderingFor(self, build):
        return self.value

    def __repr__(self):
        return f'_Lazy({repr(self.value)})'


@implementer(IRenderable)
class Interpolate(RenderableOperatorsMixin, util.ComparableMixin):

    """
    This is a marker class, used fairly widely to indicate that we
    want to interpolate build properties.
    """

    compare_attrs = ('fmtstring', 'args', 'kwargs')

    identifier_re = re.compile(r'^[\w._-]*$')

    def __init__(self, fmtstring, *args, **kwargs):
        self.fmtstring = fmtstring
        self.args = args
        self.kwargs = kwargs
        if self.args and self.kwargs:
            config.error("Interpolate takes either positional or keyword "
                         "substitutions, not both.")
        if not self.args:
            self.interpolations = {}
            self._parse(fmtstring)

    def __repr__(self):
        if self.args:
            return f'Interpolate({repr(self.fmtstring)}, *{repr(self.args)})'
        elif self.kwargs:
            return f'Interpolate({repr(self.fmtstring)}, **{repr(self.kwargs)})'
        return f'Interpolate({repr(self.fmtstring)})'

    @staticmethod
    def _parse_prop(arg):
        try:
            prop, repl = arg.split(":", 1)
        except ValueError:
            prop, repl = arg, None
        if not Interpolate.identifier_re.match(prop):
            config.error(f"Property name must be alphanumeric for prop Interpolation '{arg}'")
            prop = repl = None

        return _thePropertyDict, prop, repl

    @staticmethod
    def _parse_secret(arg):
        try:
            secret, repl = arg.split(":", 1)
        except ValueError:
            secret, repl = arg, None
        return _SecretIndexer(), secret, repl

    @staticmethod
    def _parse_src(arg):
        # TODO: Handle changes
        try:
            codebase, attr, repl = arg.split(":", 2)
        except ValueError:
            try:
                codebase, attr = arg.split(":", 1)
                repl = None
            except ValueError:
                config.error("Must specify both codebase and attribute for "
                             f"src Interpolation '{arg}'")
                return {}, None, None

        if not Interpolate.identifier_re.match(codebase):
            config.error(f"Codebase must be alphanumeric for src Interpolation '{arg}'")
            codebase = attr = repl = None
        if not Interpolate.identifier_re.match(attr):
            config.error(f"Attribute must be alphanumeric for src Interpolation '{arg}'")
            codebase = attr = repl = None
        return _SourceStampDict(codebase), attr, repl

    def _parse_worker(self, arg):
        try:
            prop, repl = arg.split(":", 1)
        except ValueError:
            prop, repl = arg, None
        return _theWorkerPropertyDict, prop, repl

    def _parse_kw(self, arg):
        try:
            kw, repl = arg.split(":", 1)
        except ValueError:
            kw, repl = arg, None
        if not Interpolate.identifier_re.match(kw):
            config.error(f"Keyword must be alphanumeric for kw Interpolation '{arg}'")
            kw = repl = None
        return _Lazy(self.kwargs), kw, repl

    def _parseSubstitution(self, fmt):
        try:
            key, arg = fmt.split(":", 1)
        except ValueError:
            config.error(f"invalid Interpolate substitution without selector '{fmt}'")
            return None

        fn = getattr(self, "_parse_" + key, None)
        if not fn:
            config.error(f"invalid Interpolate selector '{key}'")
            return None
        return fn(arg)

    @staticmethod
    def _splitBalancedParen(delim, arg):
        parenCount = 0
        for i, val in enumerate(arg):
            if val == "(":
                parenCount += 1
            if val == ")":
                parenCount -= 1
                if parenCount < 0:
                    raise ValueError
            if parenCount == 0 and val == delim:
                return arg[0:i], arg[i + 1:]
        return arg

    def _parseColon_minus(self, d, kw, repl):
        return _Lookup(d, kw,
                       default=Interpolate(repl, **self.kwargs),
                       defaultWhenFalse=False,
                       elideNoneAs='')

    def _parseColon_tilde(self, d, kw, repl):
        return _Lookup(d, kw,
                       default=Interpolate(repl, **self.kwargs),
                       defaultWhenFalse=True,
                       elideNoneAs='')

    def _parseColon_plus(self, d, kw, repl):
        return _Lookup(d, kw,
                       hasKey=Interpolate(repl, **self.kwargs),
                       default='',
                       defaultWhenFalse=False,
                       elideNoneAs='')

    def _parseColon_ternary(self, d, kw, repl, defaultWhenFalse=False):
        delim = repl[0]
        if delim == '(':
            config.error("invalid Interpolate ternary delimiter '('")
            return None
        try:
            truePart, falsePart = self._splitBalancedParen(delim, repl[1:])
        except ValueError:
            config.error(f"invalid Interpolate ternary expression '{repl[1:]}' "
                         f"with delimiter '{repl[0]}'")
            return None
        return _Lookup(d, kw,
                       hasKey=Interpolate(truePart, **self.kwargs),
                       default=Interpolate(falsePart, **self.kwargs),
                       defaultWhenFalse=defaultWhenFalse,
                       elideNoneAs='')

    def _parseColon_ternary_hash(self, d, kw, repl):
        return self._parseColon_ternary(d, kw, repl, defaultWhenFalse=True)

    def _parse(self, fmtstring):
        keys = _getInterpolationList(fmtstring)
        for key in keys:
            if key not in self.interpolations:
                d, kw, repl = self._parseSubstitution(key)
                if repl is None:
                    repl = '-'
                for pattern, fn in [
                    ("-", self._parseColon_minus),
                    ("~", self._parseColon_tilde),
                    ("+", self._parseColon_plus),
                    ("?", self._parseColon_ternary),
                    ("#?", self._parseColon_ternary_hash)
                ]:
                    junk, matches, tail = repl.partition(pattern)
                    if not junk and matches:
                        self.interpolations[key] = fn(d, kw, tail)
                        break
                if key not in self.interpolations:
                    config.error(f"invalid Interpolate default type '{repl[0]}'")

    def getRenderingFor(self, build):
        props = build.getProperties()
        if self.args:
            d = props.render(self.args)
            d.addCallback(lambda args:
                          self.fmtstring % tuple(args))
        else:
            d = props.render(self.interpolations)
            d.addCallback(lambda res:
                          self.fmtstring % res)
        return d


@implementer(IRenderable)
class Property(RenderableOperatorsMixin, util.ComparableMixin):

    """
    An instance of this class renders a property of a build.
    """

    compare_attrs = ('key', 'default', 'defaultWhenFalse')

    def __init__(self, key, default=None, defaultWhenFalse=True):
        """
        @param key: Property to render.
        @param default: Value to use if property isn't set.
        @param defaultWhenFalse: When true (default), use default value
            if property evaluates to False. Otherwise, use default value
            only when property isn't set.
        """
        self.key = key
        self.default = default
        self.defaultWhenFalse = defaultWhenFalse

    def __repr__(self):
        return f"Property({self.key})"

    def getRenderingFor(self, props):
        if self.defaultWhenFalse:
            d = props.render(props.getProperty(self.key))

            @d.addCallback
            def checkDefault(rv):
                if rv:
                    return rv
                return props.render(self.default)
            return d

        if props.hasProperty(self.key):
            return props.render(props.getProperty(self.key))
        return props.render(self.default)


@implementer(IRenderable)
class FlattenList(RenderableOperatorsMixin, util.ComparableMixin):

    """
    An instance of this class flattens all nested lists in a list
    """

    compare_attrs = ('nestedlist')

    def __init__(self, nestedlist, types=(list, tuple)):
        """
        @param nestedlist: a list of values to render
        @param types: only flatten these types. defaults to (list, tuple)
        """
        self.nestedlist = nestedlist
        self.types = types

    def getRenderingFor(self, props):
        d = props.render(self.nestedlist)

        @d.addCallback
        def flat(r):
            return flatten(r, self.types)
        return d

    def __add__(self, b):
        if isinstance(b, FlattenList):
            b = b.nestedlist
        return FlattenList(self.nestedlist + b, self.types)


@implementer(IRenderable)
class _Renderer(util.ComparableMixin):

    compare_attrs = ('fn',)

    def __init__(self, fn):
        self.fn = fn
        self.args = []
        self.kwargs = {}

    def withArgs(self, *args, **kwargs):
        new_renderer = _Renderer(self.fn)
        new_renderer.args = self.args + list(args)
        new_renderer.kwargs = dict(self.kwargs)
        new_renderer.kwargs.update(kwargs)
        return new_renderer

    @defer.inlineCallbacks
    def getRenderingFor(self, props):
        args = yield props.render(self.args)
        kwargs = yield props.render(self.kwargs)

        # We allow the renderer fn to return a renderable for convenience
        result = yield self.fn(props, *args, **kwargs)
        result = yield props.render(result)
        return result

    def __repr__(self):
        if self.args or self.kwargs:
            return f'renderer({repr(self.fn)}, args={repr(self.args)}, kwargs={repr(self.kwargs)})'
        return f'renderer({repr(self.fn)})'


def renderer(fn):
    return _Renderer(fn)


@implementer(IRenderable)
class _DefaultRenderer:

    """
    Default IRenderable adaptor. Calls .getRenderingFor if available, otherwise
    returns argument unchanged.
    """

    def __init__(self, value):
        try:
            self.renderer = value.getRenderingFor
        except AttributeError:
            self.renderer = lambda _: value

    def getRenderingFor(self, build):
        return self.renderer(build)


registerAdapter(_DefaultRenderer, object, IRenderable)


@implementer(IRenderable)
class _ListRenderer:

    """
    List IRenderable adaptor. Maps Build.render over the list.
    """

    def __init__(self, value):
        self.value = value

    def getRenderingFor(self, build):
        return defer.gatherResults([build.render(e) for e in self.value])


registerAdapter(_ListRenderer, list, IRenderable)


@implementer(IRenderable)
class _TupleRenderer:

    """
    Tuple IRenderable adaptor. Maps Build.render over the tuple.
    """

    def __init__(self, value):
        self.value = value

    def getRenderingFor(self, build):
        d = defer.gatherResults([build.render(e) for e in self.value])
        d.addCallback(tuple)
        return d


registerAdapter(_TupleRenderer, tuple, IRenderable)


@implementer(IRenderable)
class _DictRenderer:

    """
    Dict IRenderable adaptor. Maps Build.render over the keys and values in the dict.
    """

    def __init__(self, value):
        self.value = _ListRenderer(
            [_TupleRenderer((k, v)) for k, v in value.items()])

    def getRenderingFor(self, build):
        d = self.value.getRenderingFor(build)
        d.addCallback(dict)
        return d


registerAdapter(_DictRenderer, dict, IRenderable)


@implementer(IRenderable)
class Transform:

    """
    A renderable that combines other renderables' results using an arbitrary function.
    """

    def __init__(self, function, *args, **kwargs):
        if not callable(function) and not IRenderable.providedBy(function):
            config.error(
                "function given to Transform neither callable nor renderable")

        self._function = function
        self._args = args
        self._kwargs = kwargs

    @defer.inlineCallbacks
    def getRenderingFor(self, iprops):
        rfunction = yield iprops.render(self._function)
        rargs = yield iprops.render(self._args)
        rkwargs = yield iprops.render(self._kwargs)
        return rfunction(*rargs, **rkwargs)
