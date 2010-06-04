
from buildbot.schedulers.basic import Scheduler, AnyBranchScheduler, Dependent
from buildbot.schedulers.timed import Periodic, Nightly
from buildbot.schedulers.triggerable import Triggerable
from buildbot.schedulers.trysched import Try_Jobdir, Try_Userpass

_hush_pyflakes = [Scheduler, AnyBranchScheduler, Dependent,
                  Periodic, Nightly, Triggerable, Try_Jobdir, Try_Userpass]
del _hush_pyflakes
