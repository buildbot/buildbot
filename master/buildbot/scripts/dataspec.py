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


import os
import sys

from buildbot.data import connector, base
from buildbot.data.types import Identifier
from buildbot.test.fake import fakemaster
from buildbot.util import in_reactor
from buildbot.util import json
from twisted.internet import defer
import inspect

HEADER = """\
#%RAML 1.0
title: Buildbot Web API
version: v1
mediaType: application/json
traits:
    bbget:
      responses:
          200:
            body:
              application/json:
                type: responseObjects.libraries.types.<<bbtype>>
          404:
            body:
              text/plain:
                example: "not found"
    bbpost:
      body:
        type: <<reqtype>>
      responses:
          200:
            body:
              application/json:
                type: <<resptype>>
          404:
            body:
              text/plain:
                example: "not found"
"""
def createPath(paths, k):
    if k:
        key = "/" + k.pop(0)
    else:
        key = "/"
    path = paths.setdefault(key, {})
    if k:
        return createPath(path, k)
    return path

def createType(types, t):
    import yaml
    if t.name in types:
        return
    types.add(t.name)
    with open("types/%s.raml" % (t.name), "w") as f:
        f.write("#%RAML 1.0 DataType\n")
        f.write(yaml.dump(t.toRaml(), default_flow_style=False))

def dumpRaml(data, f):
    import yaml
    f.write(HEADER)
    paths = {}
    types = set()
    createType(types, Identifier())
    for k, v in sorted(data.matcher.iterPatterns()):
        path = createPath(paths, list(k))
        createType(types, v.rtype.entityType)
        if v.get.im_func != base.Endpoint.get.im_func:
            path['get'] = {'is': [ {'bbget':{ 'bbtype': v.rtype.entityType.name }}]}
        if v.control.im_func != base.Endpoint.control.im_func:
            path['post'] = {'is': [ {'bbpost':{ 'reqtype': "tbd", 'resptype': "tbd" }}]}

    f.write('types:\n')
    for t in sorted(types):
        f.write("    {0}: !include types/{0}.raml\n".format(t))
    f.write(yaml.dump(paths))

@in_reactor
@defer.inlineCallbacks
def dataspec(config):
    master = yield fakemaster.make_master()
    data = connector.DataConnector()
    data.setServiceParent(master)
    if config['out'] != '--':
        dirs = os.path.dirname(config['out'])
        if dirs and not os.path.exists(dirs):
            os.makedirs(dirs)
        f = open(config['out'], "w")
    else:
        f = sys.stdout
    if config['out'].endswith(".raml"):
        try:
            dumpRaml(data, f)
        except Exception as e:
            import traceback
            traceback.print_exc()
    else:
        endpoints = data.allEndpoints()
        if config['global'] is not None:
            f.write("window." + config['global'] + '=')
        f.write(json.dumps(endpoints, indent=2))
        f.close()
        defer.returnValue(0)
