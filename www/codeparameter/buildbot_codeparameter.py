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

from buildbot.schedulers.forcesched import TextParameter
from twisted.web import static


class CodeParameter(TextParameter):

    """A code editor using ace"""
    spec_attributes = ["mode", "height"]
    type = "code"
    mode = "text"
    height = 200


def sibpath(*elts):
    return os.path.join(os.path.dirname(__file__), *elts)


class Application(object):

    def __init__(self):
        self.description = "Buildbot CodeParameter"
        # VERSION's location differs depending on whether we're installed
        for f in sibpath('VERSION'), sibpath('static', 'VERSION'):
            if os.path.exists(f):
                self.version = open(f).read().strip()
                break
        else:
            self.version = '<unknown>'
        self.static_dir = os.path.abspath(sibpath('static'))
        self.resource = static.File(self.static_dir)


# create the interface for the setuptools entry point
ep = Application()
