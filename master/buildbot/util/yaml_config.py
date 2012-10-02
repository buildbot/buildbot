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

import yaml, os
from buildbot.util.namespace import Namespace


class YamlError(ValueError):
    """exception sent in case of any error in the yaml files
    Used to output coherent and understandable error messages
    """
    def __init__(self, path, value, message):
        ValueError.__init__(self, "%s: %s\ncode:\n%s\n"%(path, message, yaml.dump(value, indent=4)))

def YamlLoad(fn):
    path = os.path.basename(fn)
    try:
        return yaml.load(open(fn,"r").read())
    except Exception,e:
        raise YamlError(path, "", str(e))

class Type(object):
    """basic types (str, int, etc)"""
    def __init__(self, name, type, values=[]):
        self.name = name
        self.type = type
        self.values = values
    def ensure_type(self, path, val):
        if self.maybenull and val == None:
            return
        if self.type != type(val):
            raise YamlError(path, val, "should be of type %s"%(str(self.type)))
    def ensure_values(self, path, val):
        if self.values and not val in self.values:
            raise YamlError(path, val,"should be one of %s"%(" ".join(self.values)))
    def match(self, name, val):
        self.ensure_type(name, val)
        self.ensure_values(name, val)

class Container(Type):
    """container types dict,list, listofstrings, listofsetstringss, etc
    """
    def __init__(self, name, type, spec):
        self.name = name
        self.type = type
        self.spec = spec
    def match(self, name, val):
        self.ensure_type(name, val)
        self.iter_and_match(name, val)
    def match_spec(self, spec, name, val):
        spec.match(name, val)

class List(Container):
    """ Spec is a Type that is matched against all elements"""
    def iter_and_match(self, path, val):
        for i in xrange(len(val)):
            self.match_spec(self.spec, "%s[%d]"%(path,i), val[i])

class Set(List):
    """ Spec is a Type that is matched against all elements,
        each element can appear only once
    """
    def match(self, path, val):
        import copy
        Container.match(self, path, val)
        if len(val) != len(set(val)):
            _val = copy.deepcopy(val)
            while len(_val):
                v = _val.pop(0)
                if v in _val:
                    raise YamlError(path, val,"%s is included several times in a set"%(v))
class Dict(Container):
    """ spec is a dictionary of Types"""
    def iter_and_match(self, path, val):
        for k, s in self.spec.items():
            if s.required and not k in val:
                raise YamlError(path, val,"needs to define the option %s, but only has: %s"%(k, " ".join(val.keys())))
            if s.forbidden and k in val:
                raise YamlError(path, val,"option %s is forbidden"%(k))
            if s.default != None and not k in val:
                val[k] = s.default
        for k,v in val.items():
            if not k in self.spec:
                raise YamlError(path, val,"dict has key %s: but only those keys are accepted:\n%s"%(k, " ".join(self.spec.keys())))
            self.match_spec(self.spec[k], path+"."+k, v)
class Map(Container):
    """ a Map is like a named list. All elements have the same spec"""
    def iter_and_match(self, path, val):
        for k,v in val.items():
            self.match_spec(self.spec, path+"."+k, v)

class YamlConfigBuilder():
    def __init__(self, fn, additionnal_types=None, specfn=None):
        self._dict = YamlLoad(fn)
        self._ns = Namespace(self._dict)
        self.types = {}
        if not specfn:
            specfn = fn.replace(".yaml",".meta.yaml")
        if os.path.exists(specfn):
            if additionnal_types:
                self.import_types(additionnal_types)
            spec = YamlLoad(specfn)
            tname = os.path.basename(fn.replace(".yaml",""))
            t = self.create_type(tname, tname, spec["root"])
            t.match(tname, self._dict)
            # rebuild the Namespace, self._dict may contain
            # more data, filled by the default

            self._ns = Namespace(self._dict)

    def create_type(self, path,  name, spec):
        import copy
        spec = copy.deepcopy(spec)
        if not "type" in spec:
            raise YamlError(path, spec, "type spec must contain a type key")
        t = spec["type"]
        def get_component_type(t):
            t = t[t.index("of")+2:]
            # manage the case: listoflistsoflistsofsetsofstrings
            for i in "listsof setsof mapsof".split():
                if t.startswith(i):
                    return t.replace("sof","of",1)
            return t[:-1] # remove final 's'
        ret = None
        for tname, ttype in dict(string=str,integer=int,boolean=bool,float=float).items():
            if t == tname:
                kw = {}
                for k in "values".split():
                    if k in spec:
                        kw[k] =  spec[k]
                ret = Type(name, ttype, **kw)
        if ret:
            pass
        elif t.startswith("listof"):
            tname = get_component_type(t)
            spec["type"] = tname
            ret = List(name, list, self.create_type(path+"[]."+tname,tname, spec))
        elif t.startswith("mapof"):
            tname = get_component_type(t)
            spec["type"] = tname
            ret = Map(name, dict, self.create_type(path+"[]."+tname,tname, spec))
        elif t.startswith("dict"):
            kids = {}
            for k, v in spec["kids"].items():
                kids[k] = self.create_type(path+"."+k, k, v)
            ret = Dict(name, dict, kids)
        elif t.startswith("setof"):
            tname = get_component_type(t)
            spec["type"] = tname
            ret = Set(name, list, self.create_type(path+"[]."+tname,tname, spec))
        elif not t in self.types:
            raise YamlError(path, spec, "unknown type:%s"%(t))
        else:
            ret = self.types[t]
        for k in "required default forbidden maybenull".split():
            if k in spec:
                # for required and forbidden, we allow conditionnal requirement
                # depending on content of the data
                if k in "required forbidden maybenull".split() and isinstance(spec[k], str):
                    try:
                        spec[k] = eval(spec[k],dict(),dict(self=self._ns))
                    except Exception,e:
                        raise YamlError(path, spec[k], "issue with python expression in yaml:\n"+str(e))
                setattr(ret, k, spec[k])
            else:
                setattr(ret, k, None)
        return ret
    def import_types(self,fn):
        path = os.path.basename(fn)
        if os.path.exists(fn):
            for name,spec in YamlLoad(fn).items():
                self.types[name] = self.create_type(path+"."+name,name, spec)
        pass

def YamlConfig(*args,**kw):
    b = YamlConfigBuilder(*args,**kw)
    return b._ns
