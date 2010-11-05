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
Base classes for database handling
"""

class DBConnectorComponent(object):
    """
    A fixed component of the DBConnector, handling one particular aspect of the
    database.  Instances of subclasses are assigned to attributes of the
    DBConnector object, so that they are available at e.g., C{master.db.model}
    or C{master.db.changes}.  This parent class takes care of the necessary
    backlinks and other housekeeping.
    """

    connector = None

    def __init__(self, connector):
        self.connector = connector
