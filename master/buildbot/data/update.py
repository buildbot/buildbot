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

from twisted.application import service
from twisted.python import log
from buildbot.util import datetime2epoch

class UpdateComponent(service.Service):

    def __init__(self, master):
        self.setName('data.update')
        self.master = master

    def addChange(self, author=None, files=None, comments=None, is_dir=0,
            revision=None, when_timestamp=None, branch=None,
            category=None, revlink='', properties={}, repository='', codebase='',
            project='', uid=None):
        d = yield self.master.db.changes.addChange(author=author, files=files,
                            comments=comments, is_dir=is_dir,
                            revision=revision, when_timestamp=when_timestamp,
                            branch=branch, category=category,
                            revlink=revlink, properties=properties,
                            repository=repository, project=project,
                            codebase=codebase, uid=uid)
        d.addCallback(self.db.changes.getChange)
        @d.addCallback
        def produceMessage(chdict):
            msg = dict()
            msg.update(chdict)
            msg['when_timestamp'] = datetime2epoch(msg['when_timestamp'])
            self.master.mq.produce(_type="change", _event="new", **msg)
            return chdict
        @d.addCallback
        def logChanges(chdict):
            # log, being careful to handle funny characters
            msg = u"added change %s to database" % (chdict,)
            log.msg(msg.encode('utf-8', 'replace'))
            return chdict
        return d
