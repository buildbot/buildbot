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

from buildbot.util import json

class _Namespace:
    """
    A convenience class that makes a json like dict of (dicts,lists,strings,integers)
    looks like a python object allowing syntax sugar like mydict.key1.key2.key4 = 5
    this object also looks like a dict so that you can walk items(), keys() or values()

    input should always be json-able but this is checked only in pedentic mode, for
    obvious performance reason
    """
    def __init__(self,_dict):
        if self.__class__!=_Namespace:
            raise ValueError("You don't want to inherit from Namespace")
        if not type(_dict)==dict:
            raise ValueError("Expecting dict, got %s"%type(_dict))
        self.__dict__["_dict"] = _dict

# pretty printing

    def __repr__(self):
        """ pretty printed __repr__, for debugging"""
        return json.dumps(self._dict, sort_keys=True, indent=4)

# object like accessors

    def __getattr__(self,name):
        if type(name)==str and name.startswith("__"):
            raise AttributeError(name)
        if not name in self._dict:
            raise KeyError("%s not found available keys are:%s" %(name,self._dict.keys()))
        v = self._dict[name]
        return Namespace(v)

    def __setattr__(self,name, val):
        if isinstance(val, _Namespace):
            self._dict[name] = val._dict
        else:
            self._dict[name] = val

# dictionary like accessors
    def __getitem__(self, name):
        return self.__getattr__(name)
    def __setitem__(self, name, val):
        return self.__setattr__(name, val)
    def has_key(self, k):
        return self._dict.has_key(k)
    def keys(self):
        return self._dict.keys()
    def items(self):
        return map(lambda (k,v):(k,Namespace(v)), self._dict.items())
    def values(self):
        return map(lambda v:Namespace(v), self._dict.values())
    def __nonzero__(self):
        return len(self._dict)>0

# pickling
    def __getstate__(self):
        return self._dict
    def __setstate__(self,d):
        # accessing self._dict will fallback on self.__setattr__, as constructor
        # is not called by unpickling
        self.__dict__["_dict"] = d

def Namespace(v):
    """Convenience wrapper to converts any json data to _Namespace"""
    if pedantic: # we raise exception if v is not json able
        json.dumps(v)
    if type(v) == dict:
        return _Namespace(v)
    if type(v) == list:
        return [ (type(i) == dict) and _Namespace(i) or i for i in v]
    else:
        return v

def documentNamespace(n,parent=None):
    """This prints the available keys and subkeys of the data, and their types,
    meant for quick auto-documentation of big json data
    """
    s = ""
    for k,v in n._dict.items():
        if parent:
            me = parent+"."+k
        else:
            me = k
        def do_item(me, v):
            s = me + " -> "+type(v).__name__+"\n"
            if type(v)==dict:
                v = _Namespace(v)
                s += documentNamespace(v, me)
            elif type(v) == list:
                if len(v)>0:
                    v = v[0]
                    s += do_item(me+"[i]",v)
            return s
        s += do_item(me,v)
    return s

