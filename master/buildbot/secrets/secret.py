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
"""
secrets as to be used during configuration and run-time
"""


class Secret(object):
    """
    ...
    """
    def __init__(self, provider_name):
        self._provider_name = provider_name

    @property
    def provider_name(self):
        """
        where the secret is stored
        """
        return self._provider_name


class ActualSecret(object):
    """
    ...
    """
    def __init__(self, source, value, props=None):
        if props is None:
            props = dict()

        self._source = source
        self._value = value
        self._props = props

    @property
    def source(self):
        """
        source of the secret
        """
        return self._source

    @property
    def value(self):
        """
        secret value
        """
        return self._value

    @property
    def props(self):
        """
        possible extra properties
        """
        return self._props

    def __str__(self):
        return '{}: {!r}'.format(self._source, self._props)

    display = __str__
