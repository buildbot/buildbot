import sqlalchemy as sa

def upgrade(migrate_engine):

    metadata = sa.MetaData()
    metadata.bind = migrate_engine

    buildrequests_tbl = sa.Table('buildrequests', metadata, autoload=True)
    stopchain = sa.Column('stopchain', sa.SmallInteger, server_default=sa.DefaultClause("0"), nullable=False)
    stopchain.create(buildrequests_tbl)