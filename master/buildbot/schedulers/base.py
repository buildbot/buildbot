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

import logging
from zope.interface import implements
from twisted.python import failure, log
from twisted.application import service
from twisted.internet import defer
from buildbot.process.properties import Properties
from buildbot.util import ComparableMixin
from buildbot.changes import changes
from buildbot import config, interfaces, util
from buildbot.util.state import StateMixin

class BaseScheduler(service.MultiService, ComparableMixin, StateMixin):
    """
    Base class for all schedulers; this provides the equipment to manage
    reconfigurations and to handle basic scheduler state.  It also provides
    utility methods to begin various sorts of builds.

    Subclasses should add any configuration-derived attributes to
    C{base.Scheduler.compare_attrs}.
    """

    implements(interfaces.IScheduler)

    DefaultCodebases = {'':{}}

    compare_attrs = ('name', 'builderNames', 'properties', 'codebases')

    def __init__(self, name, builderNames, properties,
                 codebases = DefaultCodebases):
        """
        Initialize a Scheduler.

        @param name: name of this scheduler (used as a key for state)
        @type name: unicode

        @param builderNames: list of builders this scheduler may start
        @type builderNames: list of unicode

        @param properties: properties to add to builds triggered by this
        scheduler
        @type properties: dictionary

        @param codebases: codebases that are necessary to process the changes
        @type codebases: dict with following struct:
            key: '<codebase>'
            value: {'repository':'<repo>', 'branch':'<br>', 'revision:'<rev>'}
        """
        service.MultiService.__init__(self)
        self.name = util.ascii2unicode(name)
        "name of this scheduler; used to identify replacements on reconfig"

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
        "list of builder names to start in each buildset"

        self.properties = Properties()
        "properties that are contributed to each buildset"
        self.properties.update(properties, "Scheduler")
        self.properties.setProperty("scheduler", name, "Scheduler")

        self.objectid = None

        self.master = None

        # Set the codebases that are necessary to process the changes
        # These codebases will always result in a sourcestamp with or without changes
        if codebases is not None:
            if not isinstance(codebases, dict):
                config.error("Codebases must be a dict of dicts")
            for codebase, codebase_attrs in codebases.iteritems():
                if not isinstance(codebase_attrs, dict):
                    config.error("Codebases must be a dict of dicts")
                if (codebases != BaseScheduler.DefaultCodebases and
                   'repository' not in codebase_attrs):
                    config.error("The key 'repository' is mandatory in codebases")
        else:
            config.error("Codebases cannot be None")

        self.codebases = codebases
        
        # internal variables
        self._change_consumer = None
        self._change_consumption_lock = defer.DeferredLock()

    ## service handling

    def startService(self):
        service.MultiService.startService(self)

    def findNewSchedulerInstance(self, new_config):
        return new_config.schedulers[self.name] # should exist!

    def stopService(self):
        d = defer.maybeDeferred(self._stopConsumingChanges)
        d.addCallback(lambda _ : service.MultiService.stopService(self))
        return d


    ## status queries

    # TODO: these aren't compatible with distributed schedulers

    def listBuilderNames(self):
        "Returns the list of builder names"
        return self.builderNames

    def getPendingBuildTimes(self):
        "Returns a list of the next times that builds are scheduled, if known."
        return []

    ## change handling

    def startConsumingChanges(self, fileIsImportant=None, change_filter=None,
                              onlyImportant=False):
        """
        Subclasses should call this method from startService to register to
        receive changes.  The BaseScheduler class will take care of filtering
        the changes (using change_filter) and (if fileIsImportant is not None)
        classifying them.  See L{gotChange}.  Returns a Deferred.

        @param fileIsImportant: a callable provided by the user to distinguish
        important and unimportant changes
        @type fileIsImportant: callable

        @param change_filter: a filter to determine which changes are even
        considered by this scheduler, or C{None} to consider all changes
        @type change_filter: L{buildbot.changes.filter.ChangeFilter} instance

        @param onlyImportant: If True, only important changes, as specified by
        fileIsImportant, will be added to the buildset.
        @type onlyImportant: boolean

        """
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
            log.msg('change contains codebase %s that is not processed by'
                ' scheduler %s' % (change.codebase, self.name),
                logLevel=logging.DEBUG)
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
        d = self._change_consumption_lock.acquire()
        d.addCallback(lambda _ : self.gotChange(change, important))
        def release(x):
            self._change_consumption_lock.release()
        d.addBoth(release)
        d.addErrback(log.err, 'while processing change')

    def _stopConsumingChanges(self):
        # (note: called automatically in stopService)

        # acquire the lock change consumption lock to ensure that any change
        # consumption is complete before we are done stopping consumption
        d = self._change_consumption_lock.acquire()
        def stop(x):
            if self._change_consumer:
                self._change_consumer.stopConsuming()
                self._change_consumer = None
            self._change_consumption_lock.release()
        d.addBoth(stop)
        return d

    def gotChange(self, change, important):
        """
        Called when a change is received; returns a Deferred.  If the
        C{fileIsImportant} parameter to C{startConsumingChanges} was C{None},
        then all changes are considered important.
        The C{codebase} of the change has always an entry in the C{codebases}
        dictionary of the scheduler.

        @param change: the new change object
        @type change: L{buildbot.changes.changes.Change} instance
        @param important: true if this is an important change, according to
        C{fileIsImportant}.
        @type important: boolean
        @returns: Deferred
        """
        raise NotImplementedError

    ## starting bulids

    def addBuildsetForSourceStampsWithDefaults(self, reason, sourcestamps,
                                        properties=None, builderNames=None):
        """Create a buildset based on the supplied sourcestamps, with defaults
        applied from the scheduler's configuration.

        Sourcestamps is a list of sourcestamp dictionaries, giving the required
        parameters.  Any other defaults will be filled in from the scheduler's
        configuration.  If sourcestamps is None, only the defaults will be
        used.
        """

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
        """
        Add a buildset for the given collection of changes.  This will take the
        latest of any changes with the same codebase, and will fill in
        sourcestamps for any codebases for which no changes are included.
        """
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

    @defer.inlineCallbacks
    def addBuildsetForSourceStamps(self, sourcestamps=[], reason='',
            external_idstring=None, properties=None, builderNames=None):
        """
        Add a buildset for the given sourcestamps.

        @param sourcestamps: a list of full sourcestamp dictionaries  or
            sourcestamp IDs
        @param reason: reason for this buildset
        @type reason: unicode string
        @param external_idstring: external identifier for this buildset, or None
        @param properties: a properties object containing initial properties for
            the buildset
        @type properties: L{buildbot.process.properties.Properties}
        @param builderNames: builders to name in the buildset (defaults to
            C{self.builderNames})
        @param setid: idenitification of a set of sourcestamps
        @returns: (buildset ID, buildrequest IDs) via Deferred
        """
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

        rv = yield self.master.data.updates.addBuildset(
                scheduler=self.name, sourcestamps=sourcestamps, reason=reason,
                properties=properties_dict, builderNames=builderNames,
                external_idstring=external_idstring)
        defer.returnValue(rv)
