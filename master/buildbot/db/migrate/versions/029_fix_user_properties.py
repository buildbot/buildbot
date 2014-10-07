import sqlalchemy as sa
from migrate.changeset import constraint

def upgrade(migrate_engine):

    metadata = sa.MetaData()
    metadata.bind = migrate_engine

    user_properties_tbl = sa.Table('user_properties', metadata, autoload=True)
    users_tbl = sa.Table('users', metadata, autoload=True)

    # add missing index
    # this will allow adding other properties to users
    idx = sa.Index('user_properties_uid', user_properties_tbl.c.uid, unique=False)
    idx.create()

    if migrate_engine.dialect.name != 'mysql':
        return

    # cascade if user is deleted / updated on the db
    cons = constraint.ForeignKeyConstraint([user_properties_tbl.c.uid], [users_tbl.c.uid],
                                           onupdate="CASCADE", ondelete="CASCADE")
    cons.drop()
    cons.create()


