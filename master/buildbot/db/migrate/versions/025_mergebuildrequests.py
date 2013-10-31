import sqlalchemy as sa
from migrate.changeset import constraint

def upgrade(migrate_engine):

    metadata = sa.MetaData()
    metadata.bind = migrate_engine

    buildrequests_tbl = sa.Table('buildrequests', metadata, autoload=True)
    mergebrid = sa.Column('mergebrid', sa.Integer)
    mergebrid.create(buildrequests_tbl)
    idx = sa.Index('buildrequests_mergebrid', buildrequests_tbl.c.mergebrid, unique=False)
    idx.create()
    # Data is up to date, now force integrity
    cons = constraint.ForeignKeyConstraint([buildrequests_tbl.c.mergebrid], [buildrequests_tbl.c.id])
    cons.create()

    startbrid = sa.Column('startbrid', sa.Integer)
    startbrid.create(buildrequests_tbl)
    idx = sa.Index('buildrequests_startbrid', buildrequests_tbl.c.startbrid, unique=False)
    idx.create()
    # Data is up to date, now force integrity
    cons = constraint.ForeignKeyConstraint([buildrequests_tbl.c.startbrid], [buildrequests_tbl.c.id])
    cons.create()