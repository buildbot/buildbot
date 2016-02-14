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

from buildbot.util import sautils


def upgrade(migrate_engine):
    metadata = sa.MetaData()
    metadata.bind = migrate_engine

    # older build masters stored some of their state with an object named
    # 'master' with class 'buildbot.master.BuildMaster', while other state was
    # stored with objects named after each master itself, with class
    # BuildMaster.

    objects_table = sautils.Table('objects', metadata, autoload=True)
    object_state_table = sautils.Table('object_state', metadata, autoload=True)

    # get the old, unwanted ID
    q = sa.select([objects_table.c.id],
                  whereclause=(objects_table.c.name == 'master')
                  & (objects_table.c.class_name == 'buildbot.master.BuildMaster'))
    res = q.execute()
    old_id = res.scalar()

    # if there's no such ID, there's nothing to change
    if old_id is not None:

        # get the new ID
        q = sa.select([objects_table.c.id],
                      whereclause=objects_table.c.class_name == 'BuildMaster')
        res = q.execute()
        ids = res.fetchall()

        # if there is exactly one ID, update the existing object_states.  If
        # there are zero or multiple object_states, then we do not know which
        # master to assign last_processed_change to, so we just delete it.
        # This indicates to the master that it has processed all changes, which
        # is probably accurate.
        if len(ids) == 1:
            new_id = ids[0][0]

            # update rows with the old id to use the new id
            q = object_state_table.update(
                whereclause=(object_state_table.c.objectid == old_id))
            q.execute(objectid=new_id)
        else:
            q = object_state_table.delete(
                whereclause=(object_state_table.c.objectid == old_id))
            q.execute()

        # in either case, delete the old object row
        q = objects_table.delete(
            whereclause=(objects_table.c.id == old_id))
        q.execute()

    # and update the class name for the new rows
    q = objects_table.update(
        whereclause=(objects_table.c.class_name == 'BuildMaster'))
    q.execute(class_name='buildbot.master.BuildMaster')
