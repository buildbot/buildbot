
# compatibility wrapper. This is currently the preferred place for master.cfg
# to import from.

from buildbot.status.web.baseweb import Waterfall, WebStatus
_hush_pyflakes = [Waterfall, WebStatus]
