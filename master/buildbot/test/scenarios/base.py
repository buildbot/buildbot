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

from buildbot.data import testhooks
from buildbot.test.fake import fakedb
from twisted.internet import defer
import mock

class BaseScenario(testhooks.TestHooksScenario):
    """buildbot.test.unit.test_www.ui.BaseScenario"""
    def populateBaseDb(self):
        self.master.db.__init__(mock.Mock)
        self.master.db.insertTestData([
            fakedb.Master(id=13, name=u'inactivemaster', active=0,
                          last_active=0),
            fakedb.Master(id=14, name=u'master', active=1,
                          last_active=0),
            fakedb.Master(id=15, name=u'othermaster', active=1,
                          last_active=0),
        ])
        self.master.db.insertTestData([
            fakedb.Change(changeid=13, branch=u'trunk', revision=u'9283',
                            repository=u'svn://...', codebase=u'cbsvn',
                            project=u'world-domination'),
            fakedb.Change(changeid=14, branch=u'devel', revision=u'9284',
                            repository=u'svn://...', codebase=u'cbsvn',
                            project=u'world-domination'),
        ])
    def stopMaster(self):
        return self.master.data.updates.masterStopped(name=u'master', masterid=14)
    @defer.inlineCallbacks
    def addChanges(self):
        for rev in xrange(1,2000):
            yield self.master.data.updates.addChange(
                author=u'warner', branch=u'warnerdb',
                category=u'devel', comments=u'fix whitespace',
                files=[u'master/buildbot/__init__.py'],
                project=u'Buildbot', repository=u'git://warner',
                revision=u'0e92a098b'+str(rev), revlink=u'http://warner/0e92a098b'+str(rev),
                when_timestamp=256738404,
                properties={u'foo': 20})
