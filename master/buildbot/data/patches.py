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
from __future__ import print_function

from buildbot.data import base
from buildbot.data import types

# NOTE: patches are not available via endpoints


class Patch(base.ResourceType):

    name = "patch"
    plural = "patches"
    endpoints = []
    keyFields = ['patchid']

    class EntityType(types.Entity):
        patchid = types.Integer()
        body = types.Binary()
        level = types.Integer()
        subdir = types.String()
        author = types.String()
        comment = types.String()
    entityType = EntityType(name)
