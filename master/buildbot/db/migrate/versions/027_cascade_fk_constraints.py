import sqlalchemy as sa
from migrate import changeset
from migrate.changeset import constraint


def tryDropConst(cons):
    try:
        cons.drop()
    except:
        pass

def upgrade(migrate_engine):

    # this only applies to postgres
    if migrate_engine.dialect.name != 'mysql':
        return

    metadata = sa.MetaData()
    metadata.bind = migrate_engine

    buildrequests_tbl = sa.Table('buildrequests', metadata, autoload=True)
    buildsets_tbl = sa.Table('buildsets', metadata, autoload=True)
    sourcestampsets_tbl = sa.Table('sourcestampsets', metadata, autoload=True)
    buildrequest_claims_tbl = sa.Table('buildrequest_claims', metadata, autoload=True)
    objects_tbl = sa.Table('objects', metadata, autoload=True)
    builds_tbl = sa.Table('builds', metadata, autoload=True)
    buildset_properties_tbl = sa.Table('buildset_properties', metadata, autoload=True)
    change_files_tbl = sa.Table('change_files', metadata, autoload=True)
    changes_tbl = sa.Table('changes', metadata, autoload=True)
    change_properties_tbl = sa.Table('change_properties', metadata, autoload=True)
    change_users_tbl = sa.Table('change_users', metadata, autoload=True)
    users_tbl = sa.Table('users', metadata, autoload=True)
    mastersconfig_tbl = sa.Table('mastersconfig', metadata, autoload=True)
    object_state_tbl = sa.Table('object_state', metadata, autoload=True)
    users_info_tbl = sa.Table('users_info', metadata, autoload=True)
    patches_tbl = sa.Table('patches', metadata, autoload=True)
    sourcestamps_tbl = sa.Table('sourcestamps', metadata, autoload=True)
    sourcestamp_changes_tbl = sa.Table('sourcestamp_changes', metadata, autoload=True)
    scheduler_changes_tbl = sa.Table('scheduler_changes', metadata, autoload=True)

    # add missing FK  constraints
    # buildrequests table
    cons = constraint.ForeignKeyConstraint([buildrequests_tbl.c.mergebrid], [buildrequests_tbl.c.id],
                                           onupdate="CASCADE", ondelete="CASCADE")
    tryDropConst(cons)
    cons.create()

    cons = constraint.ForeignKeyConstraint([buildrequests_tbl.c.startbrid], [buildrequests_tbl.c.id],
                                           onupdate="CASCADE", ondelete="CASCADE")
    tryDropConst(cons)
    cons.create()

    cons = constraint.ForeignKeyConstraint([buildrequests_tbl.c.triggeredbybrid], [buildrequests_tbl.c.id],
                                           onupdate="CASCADE", ondelete="CASCADE")
    tryDropConst(cons)
    cons.create()

    cons = constraint.ForeignKeyConstraint([buildrequests_tbl.c.artifactbrid], [buildrequests_tbl.c.id],
                                           onupdate="CASCADE", ondelete="CASCADE")
    tryDropConst(cons)
    cons.create()

    cons = constraint.ForeignKeyConstraint([buildrequests_tbl.c.buildsetid], [buildsets_tbl.c.id],
                                           onupdate="CASCADE", ondelete="CASCADE")
    tryDropConst(cons)
    cons.create()

    # buildsets table
    cons = constraint.ForeignKeyConstraint([buildsets_tbl.c.sourcestampsetid], [sourcestampsets_tbl.c.id],
                                           onupdate="CASCADE", ondelete="CASCADE")
    tryDropConst(cons)
    cons.create()

    # buildrequest_claims table
    cons = constraint.ForeignKeyConstraint([buildrequest_claims_tbl.c.brid], [buildrequests_tbl.c.id],
                                           onupdate="CASCADE", ondelete="CASCADE")
    tryDropConst(cons)
    cons.create()

    cons = constraint.ForeignKeyConstraint([buildrequest_claims_tbl.c.objectid], [objects_tbl.c.id],
                                           onupdate="CASCADE", ondelete="CASCADE")
    tryDropConst(cons)
    cons.create()

    # builds table
    cons = constraint.ForeignKeyConstraint([builds_tbl.c.brid], [buildrequests_tbl.c.id],
                                           onupdate="CASCADE", ondelete="CASCADE")
    tryDropConst(cons)
    cons.create()

    # buildset_properties table
    cons = constraint.ForeignKeyConstraint([buildset_properties_tbl.c.buildsetid], [buildsets_tbl.c.id],
                                           onupdate="CASCADE", ondelete="CASCADE")
    tryDropConst(cons)
    cons.create()

    # change_files table
    cons = constraint.ForeignKeyConstraint([change_files_tbl.c.changeid], [changes_tbl.c.changeid],
                                           onupdate="CASCADE", ondelete="CASCADE")
    tryDropConst(cons)
    cons.create()

    # change_properties table
    cons = constraint.ForeignKeyConstraint([change_properties_tbl.c.changeid], [changes_tbl.c.changeid],
                                           onupdate="CASCADE", ondelete="CASCADE")
    tryDropConst(cons)
    cons.create()

    # change_users table
    cons = constraint.ForeignKeyConstraint([change_users_tbl.c.changeid], [changes_tbl.c.changeid],
                                           onupdate="CASCADE", ondelete="CASCADE")
    tryDropConst(cons)
    cons.create()

    cons = constraint.ForeignKeyConstraint([change_users_tbl.c.uid], [users_tbl.c.uid],
                                           onupdate="CASCADE", ondelete="CASCADE")
    tryDropConst(cons)
    cons.create()

    # mastersconfig table
    cons = constraint.ForeignKeyConstraint([mastersconfig_tbl.c.objectid], [objects_tbl.c.id],
                                           onupdate="CASCADE", ondelete="CASCADE")
    tryDropConst(cons)
    cons.create()

    # object_state table
    cons = constraint.ForeignKeyConstraint([object_state_tbl.c.objectid], [objects_tbl.c.id],
                                           onupdate="CASCADE", ondelete="CASCADE")
    tryDropConst(cons)
    cons.create()

    # users_info table
    cons = constraint.ForeignKeyConstraint([users_info_tbl.c.uid], [users_tbl.c.uid],
                                           onupdate="CASCADE", ondelete="CASCADE")
    tryDropConst(cons)
    cons.create()

    # sourcestamps table
    cons = constraint.ForeignKeyConstraint([sourcestamps_tbl.c.patchid], [patches_tbl.c.id],
                                           onupdate="CASCADE", ondelete="CASCADE")
    tryDropConst(cons)
    cons.create()

    cons = constraint.ForeignKeyConstraint([sourcestamps_tbl.c.sourcestampsetid], [sourcestampsets_tbl.c.id],
                                           onupdate="CASCADE", ondelete="CASCADE")
    tryDropConst(cons)
    cons.create()

    # sourcestamp_changes table
    cons = constraint.ForeignKeyConstraint([sourcestamp_changes_tbl.c.sourcestampid], [sourcestamps_tbl.c.id],
                                           onupdate="CASCADE", ondelete="CASCADE")
    tryDropConst(cons)
    cons.create()

    cons = constraint.ForeignKeyConstraint([sourcestamp_changes_tbl.c.changeid], [changes_tbl.c.changeid],
                                           onupdate="CASCADE", ondelete="CASCADE")
    tryDropConst(cons)
    cons.create()

    # scheduler_changes table
    cons = constraint.ForeignKeyConstraint([scheduler_changes_tbl.c.objectid], [objects_tbl.c.id],
                                           onupdate="CASCADE", ondelete="CASCADE")
    tryDropConst(cons)
    cons.create()

    cons = constraint.ForeignKeyConstraint([scheduler_changes_tbl.c.changeid], [changes_tbl.c.changeid],
                                           onupdate="CASCADE", ondelete="CASCADE")
    tryDropConst(cons)
    cons.create()