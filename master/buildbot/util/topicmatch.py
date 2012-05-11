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

_needsQuotesRegexp = re.compile(r'([\\.*?+{}\[\]|()])')
class TopicMatcher(object):

    def __init__(self, topics):
        def topicToRegexp(topic):
            subs = { '.' : r'\.', '*' : r'[^.]+', }

            parts = re.split(r'(\.)', topic)
            topic_re = []
            while parts:
                part = parts.pop(0)
                if part in subs:
                    topic_re.append(subs[part])
                elif part == '#':
                    if parts:
                        # pop the following '.', as it will not exist when
                        # matching zero words.
                        parts.pop(0)
                        topic_re.append(r'([^.]+\.)*')
                    else:
                        # pop the previous '.' from the regexp, as it will not
                        # exist when matching zero words
                        if topic_re:
                            topic_re.pop()
                            topic_re.append(r'(\.[^.]+)*')
                        else:
                            # topic is just '#': degenerate case
                            topic_re.append(r'.+')
                else:
                    topic_re.append(_needsQuotesRegexp.sub(r'\\\1', part))
            topic_re = ''.join(topic_re) + '$'
            return re.compile(topic_re)
        self.topics = [ topicToRegexp(t) for t in topics ]

    def matches(self, routingKey):
        for re in self.topics:
            if re.match(routingKey):
                return True
        return False
