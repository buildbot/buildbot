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

from buildbot.data import resultspec


class FakeDBComponent:
    data2db = {}

    def __init__(self, db, testcase):
        self.db = db
        self.t = testcase
        self.reactor = testcase.reactor
        self.setUp()

    def mapFilter(self, f, fieldMapping):
        field = fieldMapping[f.field].split(".")[-1]
        return resultspec.Filter(field, f.op, f.values)

    def mapOrder(self, o, fieldMapping):
        if o.startswith('-'):
            reverse, o = o[0], o[1:]
        else:
            reverse = ""
        o = fieldMapping[o].split(".")[-1]
        return reverse + o

    def applyResultSpec(self, data, rs):
        def applicable(field):
            if field.startswith('-'):
                field = field[1:]
            return field in rs.fieldMapping
        filters = [self.mapFilter(f, rs.fieldMapping)
                   for f in rs.filters if applicable(f.field)]
        order = []
        offset = limit = None
        if rs.order:
            order = [self.mapOrder(o, rs.fieldMapping)
                     for o in rs.order if applicable(o)]
        if len(filters) == len(rs.filters) and rs.order is not None and len(order) == len(rs.order):
            offset, limit = rs.offset, rs.limit
        rs = resultspec.ResultSpec(
            filters=filters, order=order, limit=limit, offset=offset)
        return rs.apply(data)
