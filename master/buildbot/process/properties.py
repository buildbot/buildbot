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

import re
import weakref
from buildbot import util
from buildbot.interfaces import IRenderable
from twisted.python.components import registerAdapter
from zope.interface import implements

class Properties(util.ComparableMixin):
    """
    I represent a set of properties that can be interpolated into various
    strings in buildsteps.

    @ivar properties: dictionary mapping property values to tuples 
        (value, source), where source is a string identifing the source
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
        self.pmap = PropertyMap(self)
        if kwargs: self.update(kwargs, "TEST")

    def __getstate__(self):
        d = self.__dict__.copy()
        del d['pmap']
        return d

    def __setstate__(self, d):
        self.__dict__ = d
        self.pmap = PropertyMap(self)
        if not hasattr(self, 'runtime'):
            self.runtime = set()

    def __contains__(self, name):
        return name in self.properties

    def __getitem__(self, name):
        """Just get the value for this property."""
        rv = self.properties[name][0]
        return rv

    def __nonzero__(self):
        return not not self.properties

    def has_key(self, name):
        return self.properties.has_key(name)

    def getProperty(self, name, default=None):
        """Get the value for the given property."""
        return self.properties.get(name, (default,))[0]

    def getPropertySource(self, name):
        return self.properties[name][1]

    def asList(self):
        """Return the properties as a sorted list of (name, value, source)"""
        l = [ (k, v[0], v[1]) for k,v in self.properties.iteritems() ]
        l.sort()
        return l

    def asDict(self):
        """Return the properties as a simple key:value dictionary"""
        return dict(self.properties)

    def __repr__(self):
        return ('Properties(**' +
                repr(dict((k,v[0]) for k,v in self.properties.iteritems())) +
                ')')

    def setProperty(self, name, value, source, runtime=False):
        self.properties[name] = (value, source)
        if runtime:
            self.runtime.add(name)

    def update(self, dict, source, runtime=False):
        """Update this object from a dictionary, with an explicit source specified."""
        for k, v in dict.items():
            self.properties[k] = (v, source)
            if runtime:
                self.runtime.add(k)

    def updateFromProperties(self, other):
        """Update this object based on another object; the other object's """
        self.properties.update(other.properties)
        self.runtime.update(other.runtime)

    def updateFromPropertiesNoRuntime(self, other):
        """Update this object based on another object, but don't
        include properties that were marked as runtime."""
        for k,v in other.properties.iteritems():
            if k not in other.runtime:
                self.properties[k] = v

class PropertyMap:
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
            prop, repl = mo.group(1,2)
            if prop in self.temp_vals:
                return self.temp_vals[prop]
            elif properties.has_key(prop):
                return properties[prop]
            else:
                return repl

        def colon_tilde(mo):
            # %(prop:~repl)s
            # if prop exists and is true (nonempty), use it; otherwise, use repl
            prop, repl = mo.group(1,2)
            if prop in self.temp_vals and self.temp_vals[prop]:
                return self.temp_vals[prop]
            elif properties.has_key(prop) and properties[prop]:
                return properties[prop]
            else:
                return repl

        def colon_plus(mo):
            # %(prop:+repl)s
            # if prop exists, use repl; otherwise, an empty string
            prop, repl = mo.group(1,2)
            if properties.has_key(prop) or prop in self.temp_vals:
                return repl
            else:
                return ''

        for regexp, fn in [
            ( self.colon_minus_re, colon_minus ),
            ( self.colon_tilde_re, colon_tilde ),
            ( self.colon_plus_re, colon_plus ),
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
        if rv is None: rv = ''
        return rv

    def add_temporary_value(self, key, val):
        'Add a temporary value (to support keyword arguments to WithProperties)'
        self.temp_vals[key] = val

    def clear_temporary_values(self):
        self.temp_vals = {}

class WithProperties(util.ComparableMixin):
    """
    This is a marker class, used fairly widely to indicate that we
    want to interpolate build properties.
    """

    implements(IRenderable)
    compare_attrs = ('fmtstring', 'args')

    def __init__(self, fmtstring, *args, **lambda_subs):
        self.fmtstring = fmtstring
        self.args = args
        if not self.args:
            self.lambda_subs = lambda_subs
            for key, val in self.lambda_subs.iteritems():
                if not callable(val):
                    raise ValueError('Value for lambda substitution "%s" must be callable.' % key)
        elif lambda_subs:
            raise ValueError('WithProperties takes either positional or keyword substitutions, not both.')

    def getRenderingFor(self, build):
        pmap = build.getProperties().pmap
        if self.args:
            strings = []
            for name in self.args:
                strings.append(pmap[name])
            s = self.fmtstring % tuple(strings)
        else:
            for k,v in self.lambda_subs.iteritems():
                pmap.add_temporary_value(k, v(build))
            s = self.fmtstring % pmap
            pmap.clear_temporary_values()
        return s


class Property(util.ComparableMixin):
    """
    An instance of this class renders a property of a build.
    """

    implements(IRenderable)

    compare_attrs = ('key','default', 'defaultWhenFalse')

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

    def getRenderingFor(self, build):
        if self.defaultWhenFalse:
            return build.getProperty(self.key) or self.default
        else:
            return build.getProperty(self.key, default=self.default)


class _DefaultRenderer:
    """
    Default IRenderable adaptor. Calls .getRenderingFor if availble, otherwise
    returns argument unchanged.
    """

    implements(IRenderable)

    def __init__(self, value):
        try:
            self.renderer = value.getRenderingFor
        except AttributeError:
            self.renderer = lambda _: value

    def getRenderingFor(self, build):
        return self.renderer(build)

registerAdapter(_DefaultRenderer, object, IRenderable)


class _ListRenderer:
    """
    List IRenderable adaptor. Maps Build.render over the list.
    """

    implements(IRenderable)

    def __init__(self, value):
        self.value = value

    def getRenderingFor(self, build):
        return [ build.render(e) for e in self.value ]

registerAdapter(_ListRenderer, list, IRenderable)


class _TupleRenderer:
    """
    Tuple IRenderable adaptor. Maps Build.render over the tuple.
    """

    implements(IRenderable)

    def __init__(self, value):
        self.value = value

    def getRenderingFor(self, build):
        return tuple([ build.render(e) for e in self.value ])

registerAdapter(_TupleRenderer, tuple, IRenderable)


class _DictRenderer:
    """
    Dict IRenderable adaptor. Maps Build.render over the keya and values in the dict.
    """

    implements(IRenderable)

    def __init__(self, value):
        self.value = value

    def getRenderingFor(self, build):
        return dict([ (build.render(k), build.render(v)) for k,v in self.value.iteritems() ])


registerAdapter(_DictRenderer, dict, IRenderable)
