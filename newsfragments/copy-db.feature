Buildbot now has ``copy-db`` script migrate all data stored in the database from one database to another.
This may be used to change database engine types.
For example a sqlite database may be migrated to Postgres or MySQL when the load and data size grows.
