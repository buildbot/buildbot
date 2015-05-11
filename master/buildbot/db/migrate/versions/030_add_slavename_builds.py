import sqlalchemy as sa

def upgrade(migrate_engine):

    metadata = sa.MetaData()
    metadata.bind = migrate_engine

    buildrequests_tbl = sa.Table('builds', metadata, autoload=True)
    slavename = sa.Column('slavename', sa.String(255), nullable=True)
    slavename.create(buildrequests_tbl)
    idx = sa.Index('builds_slavename', buildrequests_tbl.c.slavename, unique=False)
    idx.create()
