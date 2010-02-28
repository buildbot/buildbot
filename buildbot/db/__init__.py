# garbage-collection rules: the following rows can be GCed:
#  a patch that isn't referenced by any sourcestamps
#  a sourcestamp that isn't referenced by any buildsets
#  a buildrequest that isn't referenced by any buildsets
#  a buildset which is complete and isn't referenced by anything in
#   scheduler_upstream_buildsets
#  a scheduler_upstream_buildsets row that is not active
#  a build that references a non-existent buildrequest

from buildbot.db.connector import DBConnector
from buildbot.db.dbspec import DBSpec
from buildbot.db.exceptions import DBAlreadyExistsError, DatabaseNotReadyError
