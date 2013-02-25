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

from zope.interface import implements
from twisted.python import failure, log
from twisted.application import service
from twisted.internet import defer, task
from buildbot.process.properties import Properties
from buildbot.util import ComparableMixin
from buildbot.changes import changes
from buildbot import config, interfaces, util
from buildbot.util.state import StateMixin
from buildbot.data import exceptions

class BaseScheduler(service.MultiService, ComparableMixin, StateMixin):

    implements(interfaces.IScheduler)

    DEFAULT_CODEBASES = {'':{}}
    POLL_INTERVAL = 300 # 5 minutes

    compare_attrs = ('name', 'builderNames', 'properties', 'codebases')

    def __init__(self, name, builderNames, properties,
                 codebases = DEFAULT_CODEBASES):
        service.MultiService.__init__(self)
        self.name = util.ascii2unicode(name)

        ok = True
        if not isinstance(builderNames, (list, tuple)):
            ok = False
        else:
            for b in builderNames:
                if not isinstance(b, basestring):
                    ok = False
        if not ok:
            config.error(
                "The builderNames argument to a scheduler must be a list "
                  "of Builder names.")

        self.builderNames = builderNames

        self.properties = Properties()
        self.properties.update(properties, "Scheduler")
        self.properties.setProperty("scheduler", name, "Scheduler")
        self.objectid = None
        self.schedulerid = None
        self.master = None
        self.active = False

        # Set the codebases that are necessary to process the changes
        # These codebases will always result in a sourcestamp with or without changes
        if codebases is not None:
            if not isinstance(codebases, dict):
                config.error("Codebases must be a dict of dicts")
            for codebase, codebase_attrs in codebases.iteritems():
                if not isinstance(codebase_attrs, dict):
                    config.error("Codebases must be a dict of dicts")
                if (codebases != BaseScheduler.DEFAULT_CODEBASES and
                   'repository' not in codebase_attrs):
                    config.error("The key 'repository' is mandatory in codebases")
        else:
            config.error("Codebases cannot be None")

        self.codebases = codebases

        # internal variables
        self._change_consumer = None
        self._change_consumption_lock = defer.DeferredLock()

    ## activity handling

    def activate(self):
        return defer.succeed(None)

    def deactivate(self):
        return defer.succeed(None)

    ## service handling

    def startService(self):
        service.MultiService.startService(self)
        self._startActivityPolling()

    def _startActivityPolling(self):
        self._activityPollCall = task.LoopingCall(self._activityPoll)
        # plug in a clock if we have one, for tests
        if hasattr(self, 'clock'):
            self._activityPollCall.clock = self.clock
        self._activityPollDeferred = d = self._activityPollCall.start(
                self.POLL_INTERVAL, now=True)
        # this should never happen, but just in case:
        d.addErrback(log.err, 'while polling for scheduler activity:')

    def _stopActivityPolling(self):
        if self._activityPollCall:
            self._activityPollCall.stop()
            self._activityPollCall = None

    @defer.inlineCallbacks
    def _activityPoll(self):
        try:
            # just in case..
            if self.active:
                return

            upd = self.master.data.updates
            if self.schedulerid is None:
                self.schedulerid = yield upd.findSchedulerId(self.name)

            # try to claim the scheduler; if this fails, that's OK - it just
            # means we try again next time.
            try:
                yield upd.setSchedulerMaster(self.schedulerid,
                                            self.master.masterid)
            except exceptions.SchedulerAlreadyClaimedError:
                return

            self._stopActivityPolling()
            self.active = True
            try:
                yield self.activate()
            except Exception:
                # this scheduler is half-active, and noted as such in the db..
                log.err(None, 'WARNING: scheduler is only partially active')

            # Note that, in this implementation, the scheduler will never
            # become inactive again.  This may change in later versions.

        except Exception:
            # don't pass exceptions into LoopingCall, which can cause it to fail
            pass


    @defer.inlineCallbacks
    def stopService(self):
        yield service.MultiService.stopService(self)
        self._stopActivityPolling()
        # wait for the activity polling LoopingCall to complete
        yield self._activityPollDeferred
        yield self._stopConsumingChanges()
        if self.active:
            self.active = False
            yield self.deactivate()
            # unclaim the scheduler
            upd = self.master.data.updates
            yield upd.setSchedulerMaster(self.schedulerid, None)

    ## status queries

    # deprecated: these aren't compatible with distributed schedulers

    def listBuilderNames(self):
        return self.builderNames

    def getPendingBuildTimes(self):
        return []

    ## change handling

    def startConsumingChanges(self, fileIsImportant=None, change_filter=None,
                              onlyImportant=False):
        assert fileIsImportant is None or callable(fileIsImportant)

        # register for changes with the data API
        assert not self._change_consumer
        self._change_consumer = self.master.data.startConsuming(
                lambda k,m : self._changeCallback(k, m, fileIsImportant,
                                            change_filter, onlyImportant),
                {},
                ('change',))
        return defer.succeed(None)

    @defer.inlineCallbacks
    def _changeCallback(self, key, msg, fileIsImportant, change_filter,
                                onlyImportant):

        # ignore changes delivered while we're not running
        if not self._change_consumer:
            return

        # get a change object, since the API requires it
        chdict = yield self.master.db.changes.getChange(msg['changeid'])
        change = yield changes.Change.fromChdict(self.master, chdict)

        # filter it
        if change_filter and not change_filter.filter_change(change):
            return
        if change.codebase not in self.codebases:
            log.msg(format='change contains codebase %(codebase)s that is'
                'not processed by scheduler %(scheduler)s',
                codebase=change.codebase, name=self.name)
            return
        if fileIsImportant:
            try:
                important = fileIsImportant(change)
                if not important and onlyImportant:
                    return
            except:
                log.err(failure.Failure(),
                        'in fileIsImportant check for %s' % change)
                return
        else:
            important = True

        # use change_consumption_lock to ensure the service does not stop
        # while this change is being processed
        d = self._change_consumption_lock.run(self.gotChange, change, important)
        d.addErrback(log.err, 'while processing change')

    def _stopConsumingChanges(self):
        # (note: called automatically in stopService)

        # acquire the lock change consumption lock to ensure that any change
        # consumption is complete before we are done stopping consumption
        def stop():
            if self._change_consumer:
                self._change_consumer.stopConsuming()
                self._change_consumer = None
        return self._change_consumption_lock.run(stop)

    def gotChange(self, change, important):
        raise NotImplementedError

    ## starting bulids

    def addBuildsetForSourceStampsWithDefaults(self, reason, sourcestamps,
                                        properties=None, builderNames=None):

        if sourcestamps is None:
            sourcestamps = []

        # convert sourcestamps to a dictionary keyed by codebase
        stampsByCodebase = {}
        for ss in sourcestamps:
            cb = ss['codebase']
            if cb in stampsByCodebase:
                raise RuntimeError("multiple sourcestamps with same codebase")
            stampsByCodebase[cb] = ss

        # Merge codebases with the passed list of sourcestamps
        # This results in a new sourcestamp for each codebase
        stampsWithDefaults = []
        for codebase in self.codebases:
            ss = self.codebases[codebase].copy()
             # apply info from passed sourcestamps onto the configured default
             # sourcestamp attributes for this codebase.
            ss.update(stampsByCodebase.get(codebase,{}))
            stampsWithDefaults.append(ss)

        return self.addBuildsetForSourceStamps(sourcestamps=stampsWithDefaults,
                reason=reason, properties=properties,
                builderNames=builderNames)


    @defer.inlineCallbacks
    def addBuildsetForChanges(self, reason='', external_idstring=None,
            changeids=[], builderNames=None, properties=None):
        changesByCodebase = {}

        def get_last_change_for_codebase(codebase):
            return max(changesByCodebase[codebase],key = lambda change: change["changeid"])

        # Changes are retrieved from database and grouped by their codebase
        for changeid in changeids:
            chdict = yield self.master.db.changes.getChange(changeid)
            changesByCodebase.setdefault(chdict["codebase"], []).append(chdict)

        sourcestamps = []
        for codebase in self.codebases:
            if codebase not in changesByCodebase:
                # codebase has no changes
                # create a sourcestamp that has no changes
                ss = {
                    'codebase': codebase,
                    'repository': self.codebases[codebase]['repository'],
                    'branch': self.codebases[codebase].get('branch', None),
                    'revision': self.codebases[codebase].get('revision', None),
                    'project': '',
                }
            else:
                lastChange = get_last_change_for_codebase(codebase)
                ss = lastChange['sourcestampid']
            sourcestamps.append(ss)

        # add one buildset, using the calculated sourcestamps
        bsid,brids = yield self.addBuildsetForSourceStamps(
                sourcestamps=sourcestamps, reason=reason,
                external_idstring=external_idstring, builderNames=builderNames,
                properties=properties)

        defer.returnValue((bsid,brids))

    def addBuildsetForSourceStamps(self, sourcestamps=[], reason='',
            external_idstring=None, properties=None, builderNames=None):
        # combine properties
        if properties:
            properties.updateFromProperties(self.properties)
        else:
            properties = self.properties

        # apply the default builderNames
        if not builderNames:
            builderNames = self.builderNames

        # translate properties object into a dict as required by the
        # addBuildset method
        properties_dict = properties.asDict()

        return self.master.data.updates.addBuildset(
                scheduler=self.name, sourcestamps=sourcestamps, reason=reason,
                properties=properties_dict, builderNames=builderNames,
                external_idstring=external_idstring)
