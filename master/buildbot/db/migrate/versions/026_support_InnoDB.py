import sqlalchemy as sa
from migrate import changeset
from migrate.changeset import constraint

def upgrade(migrate_engine):

    # this only applies to postgres
    if migrate_engine.dialect.name != 'mysql':
        return

    metadata = sa.MetaData()
    metadata.bind = migrate_engine


    changeset.alter_column(
        sa.Column('buildername', sa.String(255), nullable=False),
        table="buildrequests",
        metadata=metadata,
        engine=migrate_engine)

    migrate_engine.execute("Alter table buildrequests ENGINE=InnoDB")
    migrate_engine.execute("Alter table buildsets ENGINE=InnoDB")
    migrate_engine.execute("Alter table sourcestampsets ENGINE=InnoDB")
    migrate_engine.execute("Alter table buildrequest_claims ENGINE=InnoDB")
    migrate_engine.execute("Alter table objects ENGINE=InnoDB")

    buildrequests_tbl = sa.Table('buildrequests', metadata, autoload=True)
    buildsets_tbl = sa.Table('buildsets', metadata, autoload=True)
    sourcestampsets_tbl = sa.Table('sourcestampsets', metadata, autoload=True)
    buildrequest_claims_tbl = sa.Table('buildrequest_claims', metadata, autoload=True)
    objects_tbl = sa.Table('objects', metadata, autoload=True)

    # add missing FK  constraints
    # buildrequests table
    cons = constraint.ForeignKeyConstraint([buildrequests_tbl.c.mergebrid], [buildrequests_tbl.c.id])
    cons.drop()
    cons.create()

    cons = constraint.ForeignKeyConstraint([buildrequests_tbl.c.startbrid], [buildrequests_tbl.c.id])
    cons.drop()
    cons.create()

    cons = constraint.ForeignKeyConstraint([buildrequests_tbl.c.triggeredbybrid], [buildrequests_tbl.c.id])
    cons.drop()
    cons.create()

    cons = constraint.ForeignKeyConstraint([buildrequests_tbl.c.artifactbrid], [buildrequests_tbl.c.id])
    cons.drop()
    cons.create()

    cons = constraint.ForeignKeyConstraint([buildrequests_tbl.c.buildsetid], [buildsets_tbl.c.id])
    cons.drop()
    cons.create()

    # buildsets table
    cons = constraint.ForeignKeyConstraint([buildsets_tbl.c.sourcestampsetid], [sourcestampsets_tbl.c.id])
    cons.drop()
    cons.create()

    # buildrequest_claims table
    cons = constraint.ForeignKeyConstraint([buildrequest_claims_tbl.c.brid], [buildrequests_tbl.c.id])
    #cons.drop()
    cons.create()

    cons = constraint.ForeignKeyConstraint([buildrequest_claims_tbl.c.objectid], [objects_tbl.c.id])
    #cons.drop()
    cons.create()
