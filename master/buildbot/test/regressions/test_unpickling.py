# This file is part of Buildbot.  Buildbot is free software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, version 2.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Copyright Buildbot Team Members
import base64

from twisted.persisted import styles
from twisted.trial import unittest

from buildbot.status.build import BuildStatus
from buildbot.status.builder import BuilderStatus
from buildbot.util import pickle
from buildbot.util.pickle import BuildStepStatus


class StatusPickles(unittest.TestCase):
    # This pickle was created with Buildbot tag v0.8.1:
    # >>> bs = BuildStatus(BuilderStatus('test'), 1)
    # >>> bss = BuildStepStatus(bs)
    # >>> pkl = pickle.dumps(dict(buildstatus=bs, buildstepstatus=bss))
    pickle_b64 = """
        KGRwMQpTJ2J1aWxkc3RlcHN0YXR1cycKcDIKKGlidWlsZGJvdC5zdGF0dXMuYnVpbGRlcgp
        CdWlsZFN0ZXBTdGF0dXMKcDMKKGRwNApTJ2xvZ3MnCnA1CihscDYKc1MndXJscycKcDcKKG
        RwOApzUydzdGF0aXN0aWNzJwpwOQooZHAxMApzUydidWlsZGJvdC5zdGF0dXMuYnVpbGRlc
        i5CdWlsZFN0ZXBTdGF0dXMucGVyc2lzdGVuY2VWZXJzaW9uJwpwMTEKSTIKc2JzUydidWls
        ZHN0YXR1cycKcDEyCihpYnVpbGRib3Quc3RhdHVzLmJ1aWxkZXIKQnVpbGRTdGF0dXMKcDE
        zCihkcDE0ClMnbnVtYmVyJwpwMTUKSTEKc1MnYnVpbGRib3Quc3RhdHVzLmJ1aWxkZXIuQn
        VpbGRTdGF0dXMucGVyc2lzdGVuY2VWZXJzaW9uJwpwMTYKSTMKc1MnZmluaXNoZWQnCnAxN
        wpJMDEKc1Mnc3RlcHMnCnAxOAoobHAxOQpzUydwcm9wZXJ0aWVzJwpwMjAKKGlidWlsZGJv
        dC5wcm9jZXNzLnByb3BlcnRpZXMKUHJvcGVydGllcwpwMjEKKGRwMjIKZzIwCihkcDIzCnN
        ic1MndGVzdFJlc3VsdHMnCnAyNAooZHAyNQpzYnMu"""
    pickle_data = base64.b64decode(pickle_b64)

    # In 0.8.1, the following persistence versions were in effect:
    #
    #   BuildStepStatus: 2
    #   BuildStatus: 3
    #   BuilderStatus: 1
    #
    # the regression that can occur here is that if the classes are renamed,
    # then older upgradeToVersionX may be run in cases where it should not;
    # this error can be "silent" since the upgrade will not fail.

    def test_upgrade(self):
        self.patch(BuildStepStatus, 'upgradeToVersion1', lambda _:
                   self.fail("BuildStepStatus.upgradeToVersion1 called"))
        self.patch(BuildStatus, 'upgradeToVersion1', lambda _:
                   self.fail("BuildStatus.upgradeToVersion1 called"))
        self.patch(BuilderStatus, 'upgradeToVersion1', lambda _:
                   self.fail("BuilderStatus.upgradeToVersion1 called"))
        pkl_result = pickle.loads(self.pickle_data)
        styles.doUpgrade()
        del pkl_result
