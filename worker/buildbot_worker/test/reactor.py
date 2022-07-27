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


from twisted.internet import threads
from twisted.python import threadpool

from buildbot_worker.test.fake.reactor import NonThreadPool
from buildbot_worker.test.fake.reactor import TestReactor


class TestReactorMixin(object):

    """
    Mix this in to get TestReactor as self.reactor which is correctly cleaned up
    at the end
    """
    def setup_test_reactor(self):

        self.patch(threadpool, 'ThreadPool', NonThreadPool)
        self.reactor = TestReactor()

        def deferToThread(f, *args, **kwargs):
            return threads.deferToThreadPool(self.reactor, self.reactor.getThreadPool(),
                                             f, *args, **kwargs)
        self.patch(threads, 'deferToThread', deferToThread)

        self.addCleanup(self.reactor.stop)
