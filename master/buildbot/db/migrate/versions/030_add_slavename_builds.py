import sqlalchemy as sa

def upgrade(migrate_engine):

    metadata = sa.MetaData()
    metadata.bind = migrate_engine

    builds_tbl = sa.Table('builds', metadata, autoload=True)
    slavename = sa.Column('slavename', sa.String(255), nullable=True)
    slavename.create(builds_tbl)
    idx = sa.Index('builds_slavename', builds_tbl.c.slavename, unique=False)
    idx.create()
