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

from buildbot import config
from buildbot import interfaces
from buildbot.changes import changes
from buildbot.process.properties import Properties
from buildbot.util.service import ClusteredService
from buildbot.util.state import StateMixin
from twisted.internet import defer
from twisted.python import failure
from twisted.python import log
from zope.interface import implements


class BaseScheduler(ClusteredService, StateMixin):

    implements(interfaces.IScheduler)

    DEFAULT_CODEBASES = {'': {}}

    compare_attrs = ClusteredService.compare_attrs + \
        ('builderNames', 'properties', 'codebases')

    def __init__(self, name, builderNames, properties,
                 codebases=DEFAULT_CODEBASES):
        ClusteredService.__init__(self, name)

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
        self.master = None

        # Set the codebases that are necessary to process the changes
        # These codebases will always result in a sourcestamp with or without
        # changes
        if codebases is not None:
            if not isinstance(codebases, dict):
                config.error("Codebases must be a dict of dicts")
            for codebase, codebase_attrs in codebases.iteritems():
                if not isinstance(codebase_attrs, dict):
                    config.error("Codebases must be a dict of dicts")
                if (codebases != BaseScheduler.DEFAULT_CODEBASES and
                        'repository' not in codebase_attrs):
                    config.error(
                        "The key 'repository' is mandatory in codebases")
        else:
            config.error("Codebases cannot be None")

        self.codebases = codebases

        # internal variables
        self._change_consumer = None
        self._change_consumption_lock = defer.DeferredLock()

    # activity handling

    def activate(self):
        return defer.succeed(None)

    def deactivate(self):
        return defer.maybeDeferred(self._stopConsumingChanges)

    # service handling

    def _getServiceId(self):
        return self.master.data.updates.findSchedulerId(self.name)

    def _claimService(self):
        return self.master.data.updates.trySetSchedulerMaster(self.serviceid,
                                                              self.master.masterid)

    def _unclaimService(self):
        return self.master.data.updates.trySetSchedulerMaster(self.serviceid,
                                                              None)

    # status queries

    # deprecated: these aren't compatible with distributed schedulers

    def listBuilderNames(self):
        return self.builderNames

    def getPendingBuildTimes(self):
        return []

    # change handling

    @defer.inlineCallbacks
    def startConsumingChanges(self, fileIsImportant=None, change_filter=None,
                              onlyImportant=False):
        assert fileIsImportant is None or callable(fileIsImportant)

        # register for changes with the data API
        assert not self._change_consumer
        self._change_consumer = yield self.master.data.startConsuming(
            lambda k, m: self._changeCallback(k, m, fileIsImportant,
                                              change_filter, onlyImportant),
            {},
            ('changes',))

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
            log.msg(format='change contains codebase %(codebase)s that is '
                    'not processed by scheduler %(name)s',
                    codebase=change.codebase, name=self.name)
            return
        if fileIsImportant:
            try:
                important = fileIsImportant(change)
                if not important and onlyImportant:
                    return
            except Exception:
                log.err(failure.Failure(),
                        'in fileIsImportant check for %s' % change)
                return
        else:
            important = True

        # use change_consumption_lock to ensure the service does not stop
        # while this change is being processed
        d = self._change_consumption_lock.run(
            self.gotChange, change, important)
        d.addErrback(log.err, 'while processing change')

    def _stopConsumingChanges(self):
        # (note: called automatically in deactivate)

        # acquire the lock change consumption lock to ensure that any change
        # consumption is complete before we are done stopping consumption
        def stop():
            if self._change_consumer:
                self._change_consumer.stopConsuming()
                self._change_consumer = None
        return self._change_consumption_lock.run(stop)

    def gotChange(self, change, important):
        raise NotImplementedError

    # starting builds

    def addBuildsetForSourceStampsWithDefaults(self, reason, sourcestamps,
                                               waited_for=False, properties=None, builderNames=None,
                                               **kw):

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
        for codebase in stampsByCodebase:
            ss = self.codebases.get(codebase, {}).copy()
            # apply info from passed sourcestamps onto the configured default
            # sourcestamp attributes for this codebase.
            ss.update(stampsByCodebase[codebase])
            stampsWithDefaults.append(ss)

        return self.addBuildsetForSourceStamps(sourcestamps=stampsWithDefaults,
                                               reason=reason, waited_for=waited_for, properties=properties,
                                               builderNames=builderNames,
                                               **kw)

    def getCodebaseDict(self, codebase):
        # Hook for subclasses to change codebase parameters when a codebase does
        # not have a change associated with it.
        try:
            return defer.succeed(self.codebases[codebase])
        except KeyError:
            return defer.fail()

    @defer.inlineCallbacks
    def addBuildsetForChanges(self, waited_for=False, reason='',
                              external_idstring=None, changeids=[], builderNames=None,
                              properties=None,
                              **kw):
        changesByCodebase = {}

        def get_last_change_for_codebase(codebase):
            return max(changesByCodebase[codebase], key=lambda change: change["changeid"])

        # Changes are retrieved from database and grouped by their codebase
        for changeid in changeids:
            chdict = yield self.master.db.changes.getChange(changeid)
            changesByCodebase.setdefault(chdict["codebase"], []).append(chdict)

        sourcestamps = []
        for codebase in self.codebases:
            if codebase not in changesByCodebase:
                # codebase has no changes
                # create a sourcestamp that has no changes
                cb = yield self.getCodebaseDict(codebase)

                ss = {
                    'codebase': codebase,
                    'repository': cb['repository'],
                    'branch': cb.get('branch', None),
                    'revision': cb.get('revision', None),
                    'project': '',
                }
            else:
                lastChange = get_last_change_for_codebase(codebase)
                ss = lastChange['sourcestampid']
            sourcestamps.append(ss)

        # add one buildset, using the calculated sourcestamps
        bsid, brids = yield self.addBuildsetForSourceStamps(
            waited_for, sourcestamps=sourcestamps, reason=reason,
            external_idstring=external_idstring, builderNames=builderNames,
            properties=properties, **kw)

        defer.returnValue((bsid, brids))

    @defer.inlineCallbacks
    def addBuildsetForSourceStamps(self, waited_for=False, sourcestamps=[],
                                   reason='', external_idstring=None, properties=None,
                                   builderNames=None, **kw):
        # combine properties
        if properties:
            properties.updateFromProperties(self.properties)
        else:
            properties = self.properties

        # apply the default builderNames
        if not builderNames:
            builderNames = self.builderNames

        # Get the builder id
        builderids = list()
        for bldr in (yield self.master.data.get(('builders', ))):
            if bldr['name'] in builderNames:
                builderids.append(bldr['builderid'])

        # translate properties object into a dict as required by the
        # addBuildset method
        properties_dict = properties.asDict()

        bsid, brids = yield self.master.data.updates.addBuildset(
            scheduler=self.name, sourcestamps=sourcestamps, reason=reason,
            waited_for=waited_for, properties=properties_dict, builderids=builderids,
            external_idstring=external_idstring, **kw)
        defer.returnValue((bsid, brids))
