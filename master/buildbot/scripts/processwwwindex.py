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

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import json
import os

import jinja2

from twisted.internet import defer

from buildbot.test.fake import fakemaster
from buildbot.util import in_reactor
from buildbot.www import auth
from buildbot.www.config import IndexResource
from buildbot.www.service import WWWService


@in_reactor
@defer.inlineCallbacks
def processwwwindex(config):
    master = yield fakemaster.make_master()
    master_service = WWWService()
    master_service.setServiceParent(master)
    if not config.get('index-file'):
        print(
            "Path to the index.html file is required with option --index-file or -i")
        defer.returnValue(1)
    path = config.get('index-file')
    if not os.path.isfile(path):
        print("Invalid path to index.html")
        defer.returnValue(2)

    main_dir = os.path.dirname(path)

    for name in master_service.apps.names:
        if name != 'base':
            pluginapp = master_service.apps.get(name)
            try:
                os.symlink(pluginapp.static_dir, os.path.join(main_dir, name))
            except OSError:
                pass

    plugins = dict((k, {}) for k in master_service.apps.names if k != "base")

    fakeconfig = {"user": {"anonymous": True}}
    fakeconfig['buildbotURL'] = master.config.buildbotURL
    fakeconfig['title'] = master.config.title
    fakeconfig['titleURL'] = master.config.titleURL
    fakeconfig['multiMaster'] = master.config.multiMaster
    fakeconfig['versions'] = IndexResource.getEnvironmentVersions()
    fakeconfig['plugins'] = plugins
    fakeconfig['auth'] = auth.NoAuth().getConfigDict()
    outputstr = ''
    with open(path) as indexfile:
        template = jinja2.Template(indexfile.read())
        outputstr = template.render(
            configjson=json.dumps(fakeconfig), config=fakeconfig)
    with open(path, 'w') as indexfile:
        indexfile.write(outputstr)
    defer.returnValue(0)
