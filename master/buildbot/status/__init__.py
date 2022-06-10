from buildbot.status import build_compat
from buildbot.status import builder_compat
from buildbot.status import buildrequest_compat
from buildbot.status import buildset_compat
from buildbot.status import master_compat

# styles.Versioned requires this, as it keys the version numbers on the fully
# qualified class name; see master/buildbot/test/regressions/test_unpickling.py
build_compat.BuildStatus.__module__ = 'buildbot.status.builder'

# add all of these classes to builder; this is a form of late binding to allow
# circular module references among the status modules
builder_compat.BuildSetStatus = buildset_compat.BuildSetStatus
builder_compat.Status = master_compat.Status
builder_compat.BuildStatus = build_compat.BuildStatus
builder_compat.BuildRequestStatus = buildrequest_compat.BuildRequestStatus
