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

import re, inspect
from twisted.python import reflect
from twisted.internet import defer
from buildbot.data import base, exceptions

# these endpoints are not intended for use in non tested masters!
# it is included in fakemaster.py

class TestHooksEndpoint(base.ControlParamsCheckMixin,base.Endpoint):
    rootLinkName = 'testhooks'
    pathPatterns = [ ( 'testhooks',) ]
    action_specs = dict(playScenario=dict(scenario=dict(re=re.compile("[a-z\.]+"),
                                                        type=str,
                                                        required=True)))
    def safeControl(self, action, args, kwargs):
        if action == "playScenario":
            return self.master.data.updates.playTestScenario(**args)
        return defer.succeed(None)

class TestHooksScenario(object):
    def __init__(self, master):
        self.master = master

class TestHooksResourceType(base.ResourceType):

    type = "testhooks"
    endpoints = [ TestHooksEndpoint]
    @base.updateMethod
    def playTestScenario(self, scenario):
        scenario = scenario.split(".")
        if len(scenario) <3:
            raise exceptions.InvalidOptionException("invalid scenario path")
        mod = ".".join(scenario[:-2])
        sym = scenario[-2]
        meth = scenario[-1]
        module = reflect.namedModule(mod)
        if not sym in dir(module):
            raise exceptions.InvalidOptionException("no class %s in module %s"%(sym,
                                                                                mod))
        obj = getattr(module, sym)
        if not(inspect.isclass(obj) and issubclass(obj, TestHooksScenario)):
            raise exceptions.InvalidOptionException(
                "class %s is not subclass of TestHooksScenario"%(meth,
                                                                 sym))
        t = obj(self.master)
        f = getattr(t, meth)
        if not f:
            raise exceptions.InvalidOptionException("no method %s in class %s"%(meth,
                                                                                sym))
        f()
        return defer.succeed(None)
