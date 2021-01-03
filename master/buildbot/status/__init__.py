from buildbot.status import builder_compat
from buildbot.status import master_compat

# add all of these classes to builder; this is a form of late binding to allow
# circular module references among the status modules
builder_compat.Status = master_compat.Status
