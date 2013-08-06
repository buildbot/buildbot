import sqlalchemy as sa

def upgrade(migrate_engine):
    metadata = sa.MetaData()
    metadata.bind = migrate_engine

    buildrequests_table = sa.Table('buildrequests', metadata, autoload=True)

	# boolean indicating whether there is a step blocking, waiting for this request to complete
    waited_for = sa.Column('waited_for', sa.SmallInteger,
        server_default=sa.DefaultClause("0"))
    waited_for.create(buildrequests_table)
