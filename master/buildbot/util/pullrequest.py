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


from fnmatch import fnmatch


class PullRequestMixin:
    external_property_whitelist = []
    external_property_denylist = []

    def extractProperties(self, payload):
        def flatten(properties, base, info_dict):
            for k, v in info_dict.items():
                name = ".".join([base, k])
                if name in self.external_property_denylist:
                    continue
                if isinstance(v, dict):
                    flatten(properties, name, v)
                elif any(fnmatch(name, expr) for expr in self.external_property_whitelist):
                    properties[name] = v

        properties = {}
        flatten(properties, self.property_basename, payload)
        return properties
