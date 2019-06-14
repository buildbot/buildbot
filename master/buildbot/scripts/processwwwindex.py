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


import json
import os
import shutil

import jinja2

from twisted.internet import defer

from buildbot.test.fake import fakemaster
from buildbot.util import in_reactor
from buildbot.www import auth
from buildbot.www.config import IndexResource
from buildbot.www.service import WWWService


def get_www_plugins_config(master):
    all_apps = [(name, master.apps.get(name)) for name in master.apps.names]
    all_apps = [(name, app) for name, app in all_apps if name != "base"]
    all_apps = [(name, app) for name, app in all_apps if app.ui]
    return {name: {} for name, _ in all_apps}


@in_reactor
@defer.inlineCallbacks
def processwwwindex(config):
    master = yield fakemaster.make_master(None, wantRealReactor=True)
    master_service = WWWService()
    master_service.setServiceParent(master)

    if not config.get('src-dir'):
        print("Path to the source directory is with option --src-dir")
        return 1
    if not config.get('dst-dir'):
        print("Path to the destination directory is with option --dst-dir")
        return 1

    src_dir = config.get('src-dir')
    dst_dir = config.get('dst-dir')

    if not os.path.isdir(src_dir):
        print("Invalid path to source directory")
        return 2

    if os.path.exists(dst_dir):
        print('Removing {}'.format(dst_dir))
        if os.path.isfile(dst_dir):
            os.remove(dst_dir)
        elif os.path.isdir(dst_dir):
            shutil.rmtree(dst_dir)

    shutil.copytree(src_dir, dst_dir)

    for name in master_service.apps.names:
        if name != 'base':
            pluginapp = master_service.apps.get(name)
            try:
                os.symlink(pluginapp.static_dir, os.path.join(dst_dir, name))
            except OSError:
                print('Could not link static dir of plugin {}'.format(name))

    fakeconfig = {"user": {"anonymous": True}}
    fakeconfig['buildbotURL'] = master.config.buildbotURL
    fakeconfig['title'] = master.config.title
    fakeconfig['titleURL'] = master.config.titleURL
    fakeconfig['multiMaster'] = master.config.multiMaster
    fakeconfig['versions'] = IndexResource.getEnvironmentVersions()
    fakeconfig['plugins'] = get_www_plugins_config(master_service)
    fakeconfig['auth'] = auth.NoAuth().getConfigDict()

    indexfile_path = os.path.join(dst_dir, 'index.html')
    with open(indexfile_path) as indexfile:
        template = jinja2.Template(indexfile.read())
        outputstr = template.render(configjson=json.dumps(fakeconfig), config=fakeconfig)

    with open(indexfile_path, 'w') as indexfile:
        indexfile.write(outputstr)
    return 0
