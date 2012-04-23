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

import re

class Endpoint(object):

    # set the pathPattern to the pattern that should trigger this endpoint
    pathPattern = None

    # the mq topic corresponding to this path, with %(..)s safely substituted
    # from the path kwargs; for more complex cases, override
    # getSubscriptionTopic.

    pathTopicTemplate = None

    def __init__(self, master):
        self.master = master

    def get(self, options, kwargs):
        raise NotImplementedError

    def control(self, action, args, kwargs):
        raise NotImplementedError

    def getSubscriptionTopic(self, options, kwargs):
        if self.pathTopicTemplate:
            if '%'  not in self.pathTopicTemplate:
                return self.pathTopicTemplate
            safekwargs = SafeDict(kwargs)
            return self.pathTopicTemplate % safekwargs


class SafeDict(object):
    # utility class to allow %-substitution with the results not containing
    # topic metacharacters (.*#)

    def __init__(self, dict):
        self.dict = dict

    metacharacters_re = re.compile('[.*#]')
    def __getitem__(self, k):
        return self.metacharacters_re.sub('_', self.dict[k])


class Link(object):

    __slots__ = [ 'path' ]

    # a link to another resource, specified as a path
    def __init__(self, path):
        self.path = path

    def __repr__(self):
        return "Link(%r)" % (self.path,)
