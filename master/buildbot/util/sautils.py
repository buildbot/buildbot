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

import sqlalchemy as sa
from sqlalchemy.ext import compiler
from sqlalchemy.sql.expression import Executable, ClauseElement

# from http://www.sqlalchemy.org/docs/core/compiler.html#compiling-sub-elements-of-a-custom-expression-construct

class InsertFromSelect(Executable, ClauseElement):
    def __init__(self, table, select):
        self.table = table
        self.select = select

@compiler.compiles(InsertFromSelect)
def _visit_insert_from_select(element, compiler, **kw):
    return "INSERT INTO %s %s" % (
        compiler.process(element.table, asfrom=True),
        compiler.process(element.select)
    )

def sa_version():
    if hasattr(sa, '__version__'):
        def tryint(s):
            try:
                return int(s)
            except:
                return -1
        return tuple(map(tryint, sa.__version__.split('.')))
    return (0,0,0) # "it's old"
