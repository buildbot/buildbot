import sqlalchemy as sa
from migrate.changeset import constraint


def upgrade(migrate_engine):
    metadata = sa.MetaData()
    metadata.bind = migrate_engine

    user_props = sa.Table("user_properties", metadata,
                          sa.Column("uid", sa.Integer, nullable=False),
                          sa.Column('prop_type', sa.String(128), nullable=False),
                          sa.Column('prop_data', sa.String(128), nullable=False),
                          sa.UniqueConstraint('uid', 'prop_type', name='users_uid_prop_type'),
    )
    user_props.create()

    idx = sa.Index('user_props_attrs', user_props.c.prop_type, user_props.c.prop_data)
    idx.create()

    users_tbl = sa.Table('users', metadata, autoload=True)

    cons = constraint.ForeignKeyConstraint([user_props.c.uid], [users_tbl.c.uid])
    cons.create()