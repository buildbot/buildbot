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

from __future__ import annotations

from twisted.internet import defer

from buildbot.data import base
from buildbot.data import types
import glob
import os


class MessageInfoEndpoint(base.Endpoint):
    kind = base.EndpointKind.COLLECTION
    pathPatterns = """
        /messagesinfo
    """

    def read_txt_files_in_directory(self, dir_path):
        path = os.path.join(dir_path, "*.txt")
        all_files = glob.glob(path)
        for file in all_files:
            with open(file) as f:
                yield {"filename": file, "message": f.read()}


    @defer.inlineCallbacks
    def get(self, resltSpec, kwargs):
        config = self.master.config
        messages = yield self.read_txt_files_in_directory(config.messageInfoDir)
        return [ msg for msg in messages ]



class MessageInfo(base.ResourceType):
    name = "messageinfo"
    plural = "messagesinfo"
    endpoints = [MessageInfoEndpoint]
    subresources = ["Change"]

    class EntityType(types.Entity):
        filename = types.String()
        message = types.String()


    entityType = EntityType(name, 'MessageInfo')
