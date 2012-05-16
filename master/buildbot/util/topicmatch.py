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

class TopicMatcher(object):

    def __init__(self, topics):
        self.topics = topics

    def _matchTopic(self, topic, msg):
        try:
            for key in topic:
                if topic[key] != msg[key]:
                    return False
            return True
        except KeyError:
            return False

    def matches(self, routingKey):
        for topic in self.topics:
            if self._matchTopic(topic, routingKey):
                return True
        return False
