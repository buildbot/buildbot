
# compatibility wrapper. This is currently the preferred place for master.cfg
# to import from.

from buildbot.status.web.baseweb import WebStatus
_hush_pyflakes = [WebStatus]
