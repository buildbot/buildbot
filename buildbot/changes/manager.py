# ***** BEGIN LICENSE BLOCK *****
# Version: MPL 1.1/GPL 2.0/LGPL 2.1
#
# The contents of this file are subject to the Mozilla Public License Version
# 1.1 (the "License"); you may not use this file except in compliance with
# the License. You may obtain a copy of the License at
# http://www.mozilla.org/MPL/
#
# Software distributed under the License is distributed on an "AS IS" basis,
# WITHOUT WARRANTY OF ANY KIND, either express or implied. See the License
# for the specific language governing rights and limitations under the
# License.
#
# The Original Code is Mozilla-specific Buildbot steps.
#
# The Initial Developer of the Original Code is
# Mozilla Foundation.
# Portions created by the Initial Developer are Copyright (C) 2009
# the Initial Developer. All Rights Reserved.
#
# Contributor(s):
#   Brian Warner <warner@lothar.com>
#
# Alternatively, the contents of this file may be used under the terms of
# either the GNU General Public License Version 2 or later (the "GPL"), or
# the GNU Lesser General Public License Version 2.1 or later (the "LGPL"),
# in which case the provisions of the GPL or the LGPL are applicable instead
# of those above. If you wish to allow use of your version of this file only
# under the terms of either the GPL or the LGPL, and not to allow others to
# use your version of this file under the terms of the MPL, indicate your
# decision by deleting the provisions above and replace them with the notice
# and other provisions required by the GPL or the LGPL. If you do not delete
# the provisions above, a recipient may use your version of this file under
# the terms of any one of the MPL, the GPL or the LGPL.
#
# ***** END LICENSE BLOCK *****

from zope.interface import implements
from twisted.python import log
from twisted.internet import defer
from twisted.application import service

from buildbot import interfaces, util

class ChangeManager(service.MultiService):

    """This is the master-side service which receives file change
    notifications from a VCS. It keeps a log of these changes, enough to
    provide for the HTML waterfall display, and to tell
    temporarily-disconnected bots what they missed while they were
    offline.

    Change notifications come from two different kinds of sources. The first
    is a PB service (servicename='changemaster', perspectivename='change'),
    which provides a remote method called 'addChange', which should be
    called with a dict that has keys 'filename' and 'comments'.

    The second is a list of objects derived from the 
    L{buildbot.changes.base.ChangeSource} class. These are added with 
    .addSource(), which also sets the .changemaster attribute in the source 
    to point at the ChangeMaster. When the application begins, these will 
    be started with .start() . At shutdown time, they will be terminated 
    with .stop() . They must be persistable. They are expected to call 
    self.changemaster.addChange() with Change objects.

    There are several different variants of the second type of source:

      - L{buildbot.changes.mail.MaildirSource} watches a maildir for CVS
        commit mail. It uses DNotify if available, or polls every 10
        seconds if not.  It parses incoming mail to determine what files
        were changed.

      - L{buildbot.changes.freshcvs.FreshCVSSource} makes a PB
        connection to the CVSToys 'freshcvs' daemon and relays any
        changes it announces.

    """

    implements(interfaces.IEventSource)

    changeHorizon = 0
    name = "changemanager"

    def __init__(self):
        service.MultiService.__init__(self)
        self._cache = util.LRUCache()

    def addSource(self, source):
        assert interfaces.IChangeSource.providedBy(source)
        assert service.IService.providedBy(source)
        source.setServiceParent(self)

    def removeSource(self, source):
        assert source in self
        return defer.maybeDeferred(source.disownServiceParent)

    def addChange(self, change):
        """Deliver a file change event. The event should be a Change object.
        This method will timestamp the object as it is received."""
        log.msg("adding change, who %s, %d files, rev=%s, branch=%s, repository=%s, "
                "comments %s, category %s" % (change.who, len(change.files),
                                              change.revision, change.branch, change.repository,
                                              change.comments, change.category))

        #self.pruneChanges() # use self.changeHorizon
        # for now, add these in the background, without waiting for it. TODO:
        # return a Deferred.
        #self.queue.add(db.runInteraction, self.addChangeToDatabase, change)

        # this sets change.number, if it wasn't already set (by the
        # migration-from-pickle code). It also fires a notification which
        # wakes up the Schedulers.
        self.parent.addChange(change)


    # IEventSource methods

    def eventGenerator(self, branches=[], categories=[], committers=[], minTime=0):
        return self.parent.db.changeEventGenerator(branches, categories,
                                                   committers, minTime)

    def getChangeNumberedNow(self, changeid, t=None):
        return self.parent.db.getChangeNumberedNow(changeid, t)
    def getChangeByNumber(self, changeid):
        return self.parent.db.getChangeByNumber(changeid)
    def getChangesGreaterThan(self, last_changeid, t=None):
        return self.parent.db.getChangesGreaterThan(last_changeid, t)
    def getChangesByNumber(self, changeids):
        return self.parent.db.getChangesByNumber(changeids)
    def getLatestChangeNumberNow(self, t=None):
        return self.parent.db.getLatestChangeNumberNow(t)
