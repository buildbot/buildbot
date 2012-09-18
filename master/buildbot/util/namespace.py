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

pedantic = False
class __Namespace(dict):
    """
    A convenience class that makes a json like dict of (dicts,lists,strings,integers)
    looks like a python object allowing syntax sugar like mydict.key1.key2.key4 = 5
    this object also looks like a dict so that you can walk items(), keys() or values()

    input should always be json-able but this is checked only in pedentic mode, for
    obvious performance reason
    """

# pretty printing

    def __repr__(self):
        """ pretty printed __repr__, for debugging"""
        return json.dumps(self, sort_keys=True, indent=4)

# object like accessors

    def __getattr__(self,name):
        return self[name]
    def __setattr__(self,name, val):
        self[name] = val

# dictionary like accessors
    def __setitem__(self, name, val):
        return dict.__setitem__(self,name,Namespace(val))
    def __getstate__(self):
        return self
    def __setstate__(self,_dict):
        self.__init__(_dict)
def _Namespace(v):
    if v.__repr__ == __Namespace.__repr__:
        return
    # does not work, dict methods cannot be hijacked like this.
    v.__repr__ = __Namespace.__repr__
    v.__getattr__ = __Namespace.__getattr__
    v.__setitem__ = __Namespace.__setitem__
    v.__getstate__ = __Namespace.__getstate__
    v.__setstate__ = __Namespace.__setstate__
    v.__setattr__ = __Namespace.__setattr__

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
    for k,v in n.items():
        if parent:
            me = parent+"."+k
        else:
            me = k
        def do_item(me, v):
            t = type(v).__name__
            if t == "_Namespace":
                t = "dict"
            s = me + " -> "+t+"\n"
            if isinstance(v,dict):
                v = _Namespace(v)
                s += documentNamespace(v, me)
            elif type(v) == list:
                if len(v)>0:
                    v = v[0]
                    s += do_item(me+"[i]",v)
            return s
        s += do_item(me,v)
    return s

