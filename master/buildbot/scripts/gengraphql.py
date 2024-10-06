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

from buildbot.data import connector
from buildbot.data.graphql import GraphQLConnector
from buildbot.test.fake import fakemaster
from buildbot.util import in_reactor


@in_reactor
async def gengraphql(config):
    master = await fakemaster.make_master(None, wantRealReactor=True)
    data = connector.DataConnector()
    await data.setServiceParent(master)
    graphql = GraphQLConnector()
    await graphql.setServiceParent(master)
    graphql.data = data
    master.config.www = {"graphql": {'debug': True}}
    graphql.reconfigServiceWithBuildbotConfig(master.config)
    await master.startService()
    if config['out'] != '--':
        dirs = os.path.dirname(config['out'])
        if dirs and not os.path.exists(dirs):
            os.makedirs(dirs)
        f = open(config['out'], "w", encoding='utf-8')
    else:
        f = sys.stdout
    schema = graphql.get_schema()
    f.write(schema)
    f.close()
    await master.stopService()
    return 0
