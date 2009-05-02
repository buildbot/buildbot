import re
import weakref
from buildbot import util

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
        self.pmap = PropertyMap(self)
        if kwargs: self.update(kwargs, "TEST")

    def __getstate__(self):
        d = self.__dict__.copy()
        del d['pmap']
        return d

    def __setstate__(self, d):
        self.__dict__ = d
        self.pmap = PropertyMap(self)

    def __contains__(self, name):
        return name in self.properties

    def __getitem__(self, name):
        """Just get the value for this property."""
        rv = self.properties[name][0]
        return rv

    def has_key(self, name):
        return self.properties.has_key(name)

    def getProperty(self, name, default=None):
        """Get the value for the given property."""
        return self.properties.get(name, (default,))[0]

    def getPropertySource(self, name):
        return self.properties[name][1]

    def asList(self):
        """Return the properties as a sorted list of (name, value, source)"""
        l = [ (k, v[0], v[1]) for k,v in self.properties.items() ]
        l.sort()
        return l

    def __repr__(self):
        return repr(dict([ (k,v[0]) for k,v in self.properties.iteritems() ]))

    def setProperty(self, name, value, source):
        self.properties[name] = (value, source)

    def update(self, dict, source):
        """Update this object from a dictionary, with an explicit source specified."""
        for k, v in dict.items():
            self.properties[k] = (v, source)

    def updateFromProperties(self, other):
        """Update this object based on another object; the other object's """
        self.properties.update(other.properties)

    def render(self, value):
        """
        Return a variant of value that has any WithProperties objects
        substituted.  This recurses into Python's compound data types.
        """
        # we use isinstance to detect Python's standard data types, and call
        # this function recursively for the values in those types
        if isinstance(value, (str, unicode)):
            return value
        elif isinstance(value, WithProperties):
            return value.render(self.pmap)
        elif isinstance(value, list):
            return [ self.render(e) for e in value ]
        elif isinstance(value, tuple):
            return tuple([ self.render(e) for e in value ])
        elif isinstance(value, dict):
            return dict([ (self.render(k), self.render(v)) for k,v in value.iteritems() ])
        else:
            return value

class PropertyMap:
    """
    Privately-used mapping object to implement WithProperties' substitutions,
    including the rendering of None as ''.
    """
    colon_minus_re = re.compile(r"(.*):-(.*)")
    colon_plus_re = re.compile(r"(.*):\+(.*)")
    def __init__(self, properties):
        # use weakref here to avoid a reference loop
        self.properties = weakref.ref(properties)

    def __getitem__(self, key):
        properties = self.properties()
        assert properties is not None

        # %(prop:-repl)s
        # if prop exists, use it; otherwise, use repl
        mo = self.colon_minus_re.match(key)
        if mo:
            prop, repl = mo.group(1,2)
            if properties.has_key(prop):
                rv = properties[prop]
            else:
                rv = repl
        else:
            # %(prop:+repl)s
            # if prop exists, use repl; otherwise, an empty string
            mo = self.colon_plus_re.match(key)
            if mo:
                prop, repl = mo.group(1,2)
                if properties.has_key(prop):
                    rv = repl
                else:
                    rv = ''
            else:
                rv = properties[key]

        # translate 'None' to an empty string
        if rv is None: rv = ''
        return rv

class WithProperties(util.ComparableMixin):
    """
    This is a marker class, used fairly widely to indicate that we
    want to interpolate build properties.
    """

    compare_attrs = ('fmtstring', 'args')

    def __init__(self, fmtstring, *args):
        self.fmtstring = fmtstring
        self.args = args

    def render(self, pmap):
        if self.args:
            strings = []
            for name in self.args:
                strings.append(pmap[name])
            s = self.fmtstring % tuple(strings)
        else:
            s = self.fmtstring % pmap
        return s
