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
from twisted.internet import defer
from buildbot.process.properties import Properties
from buildbot.util import ComparableMixin
from buildbot.changes import changes
from buildbot import config, interfaces

class BaseScheduler(service.MultiService, ComparableMixin):
    """
    Base class for all schedulers; this provides the equipment to manage
    reconfigurations and to handle basic scheduler state.  It also provides
    utility methods to begin various sorts of builds.

    Subclasses should add any configuration-derived attributes to
    C{base.Scheduler.compare_attrs}.
    """

    implements(interfaces.IScheduler)

    compare_attrs = ('name', 'builderNames', 'properties', 'codebases')
    allowed_codebase_attrs = set(['repository', 'branch', 'revision'])

    def __init__(self, name, builderNames, properties, codebases = None):
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
            {'codebase':{'repository':'', 'branch':'', 'revision:''}

        @param consumeChanges: true if this scheduler wishes to be informed
        about the addition of new changes.  Defaults to False.  This should
        be passed explicitly from subclasses to indicate their interest in
        consuming changes.
        @type consumeChanges: boolean
        """
        service.MultiService.__init__(self)
        self.name = name
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

        # Set the other codebases that are necessary to process the changes
        # These codebases will always result in a sourcestamp with or without changes
        if codebases:
            try:
                for codebase, values in codebases.iteritems():
                    codebase_attrs = set(values.keys())
                    # (A,B,D) & (A,B,C) = (A,B) != (A,B,C)
                    if not codebase_attrs.issubset(self.allowed_codebase_attrs):
                        raise ValueError, "codebase %s has invalid values %s" % (codebase,codebase_attrs)
            except Exception as ex:
                raise ValueError, "Codebases does not have the correct dictionary struct: %s" % ex
        self.codebases = codebases
        
        # internal variables
        self._change_subscription = None
        self._change_consumption_lock = defer.DeferredLock()
        self._objectid = None

    ## service handling

    def startService(self):
        service.MultiService.startService(self)

    def findNewSchedulerInstance(self, new_config):
        return new_config.schedulers[self.name] # should exist!

    def stopService(self):
        d = defer.maybeDeferred(self._stopConsumingChanges)
        d.addCallback(lambda _ : service.MultiService.stopService(self))
        return d

    ## state management

    @defer.deferredGenerator
    def getState(self, *args, **kwargs):
        """
        For use by subclasses; get a named state value from the scheduler's
        state, defaulting to DEFAULT.

        @param name: name of the value to retrieve
        @param default: (optional) value to return if C{name} is not present
        @returns: state value via a Deferred
        @raises KeyError: if C{name} is not present and no default is given
        @raises TypeError: if JSON parsing fails
        """
        # get the objectid, if not known
        if self._objectid is None:
            wfd = defer.waitForDeferred(
                self.master.db.state.getObjectId(self.name,
                                        self.__class__.__name__))
            yield wfd
            self._objectid = wfd.getResult()

        wfd = defer.waitForDeferred(
            self.master.db.state.getState(self._objectid, *args, **kwargs))
        yield wfd
        yield wfd.getResult()

    @defer.deferredGenerator
    def setState(self, key, value):
        """
        For use by subclasses; set a named state value in the scheduler's
        persistent state.  Note that value must be json-able.

        @param name: the name of the value to change
        @param value: the value to set - must be a JSONable object
        @param returns: Deferred
        @raises TypeError: if JSONification fails
        """
        # get the objectid, if not known
        if self._objectid is None:
            wfd = defer.waitForDeferred(
                self.master.db.state.getObjectId(self.name,
                                        self.__class__.__name__))
            yield wfd
            self._objectid = wfd.getResult()

        wfd = defer.waitForDeferred(
            self.master.db.state.setState(self._objectid, key, value))
        yield wfd
        wfd.getResult()

    ## status queries

    # TODO: these aren't compatible with distributed schedulers

    def listBuilderNames(self):
        "Returns the list of builder names"
        return self.builderNames

    def getPendingBuildTimes(self):
        "Returns a list of the next times that builds are scheduled, if known."
        return []

    ## codebase related methods
    ## to have the code less dependent from input structure
    def getRepository(self, codebase):
        return self.codebases[codebase]['repository']

    def getBranch(self, codebase):
        if 'branch' in self.codebases[codebase]:
            return self.codebases[codebase]['branch']
        else:
            return None

    def getRevision(self, codebase):
        return self.codebases[codebase]['revision']
    
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

        # register for changes with master
        assert not self._change_subscription
        def changeCallback(change):
            # ignore changes delivered while we're not running
            if not self._change_subscription:
                return

            if change_filter and not change_filter.filter_change(change):
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
        self._change_subscription = self.master.subscribeToChanges(changeCallback)

        return defer.succeed(None)

    def _stopConsumingChanges(self):
        # (note: called automatically in stopService)

        # acquire the lock change consumption lock to ensure that any change
        # consumption is complete before we are done stopping consumption
        d = self._change_consumption_lock.acquire()
        def stop(x):
            if self._change_subscription:
                self._change_subscription.unsubscribe()
                self._change_subscription = None
            self._change_consumption_lock.release()
        d.addBoth(stop)
        return d

    def gotChange(self, change, important):
        """
        Called when a change is received; returns a Deferred.  If the
        C{fileIsImportant} parameter to C{startConsumingChanges} was C{None},
        then all changes are considered important.

        @param change: the new change object
        @type change: L{buildbot.changes.changes.Change} instance
        @param important: true if this is an important change, according to
        C{fileIsImportant}.
        @type important: boolean
        @returns: Deferred
        """
        raise NotImplementedError

    ## starting bulids

    @defer.deferredGenerator
    def addBuildsetForLatest(self, reason='', external_idstring=None,
                        branch=None, repository='', project='',
                        builderNames=None, properties=None):
        """
        Add a buildset for the 'latest' source in the given branch,
        repository, and project.  This will create a relative sourcestamp for
        the buildset.

        This method will add any properties provided to the scheduler
        constructor to the buildset, and will call the master's addBuildset
        method with the appropriate parameters.

        @param reason: reason for this buildset
        @type reason: unicode string
        @param external_idstring: external identifier for this buildset, or None
        @param branch: branch to build (note that None often has a special meaning)
        @param repository: repository name for sourcestamp
        @param project: project name for sourcestamp
        @param builderNames: builders to name in the buildset (defaults to
            C{self.builderNames})
        @param properties: a properties object containing initial properties for
            the buildset
        @type properties: L{buildbot.process.properties.Properties}
        @returns: (buildset ID, buildrequest IDs) via Deferred
        """
        # Define setid for this set of changed repositories
        wfd = defer.waitForDeferred(self.master.db.sourcestampsets.addSourceStampSet())
        yield wfd
        setid = wfd.getResult()

        wfd = defer.waitForDeferred(self.master.db.sourcestamps.addSourceStamp(
                branch=branch, revision=None, repository=repository,
                project=project, sourcestampsetid=setid))
        yield wfd
        wfd.getResult()

        wfd = defer.waitForDeferred(self.addBuildsetForSourceStamp(
                                setid=setid, reason=reason,
                                external_idstring=external_idstring,
                                builderNames=builderNames,
                                properties=properties))
        yield wfd
        yield wfd.getResult()


    @defer.deferredGenerator
    def addBuildsetForChanges(self, reason='', external_idstring=None,
            changeids=[], builderNames=None, properties=None):
        assert changeids is not []
        chDict = {}

        def getChange(changeid = None):
            d = self.master.db.changes.getChange(changeid)
            def chdict2change(chdict):
                if not chdict:
                    return None
                return changes.Change.fromChdict(self.master, chdict)
            d.addCallback(chdict2change)
            return d

        def groupChange(change):
            if change.codebase not in chDict:
                chDict[change.codebase] = []
            chDict[change.codebase].append(change)

        def get_changeids_from_codebase(codebase):
            return [c.number for c in chDict[codebase]]

        def get_last_change_for_codebase(codebase):
            lastChange = None
            maxNr = -1
            for c in chDict[codebase]:
                if c.number > maxNr:
                    lastChange = c
                    maxNr = c.number
            return lastChange

        def create_sourcestamp(changeids, change, setid = None):
            return self.master.db.sourcestamps.addSourceStamp(
                    codebase=change.codebase,
                    repository=change.repository,
                    branch=change.branch,
                    revision=change.revision,
                    project=change.project,
                    changeids=changeids,
                    sourcestampsetid=setid)

        def create_sourcestamp_without_changes(setid, codebase):
            repository = self.getRepository(codebase)
            branch = self.getBranch(codebase)
            revision = self.getRevision(codebase)
            return self.master.db.sourcestamps.addSourceStamp(
                    codebase=codebase,
                    repository=repository,
                    branch=branch,
                    revision=revision,
                    project='no project', #HBX
                    changeids=set(),
                    sourcestampsetid=setid)

        # Define setid for this set of changed repositories
        wfd = defer.waitForDeferred(self.master.db.sourcestampsets.addSourceStampSet())
        yield wfd
        setid = wfd.getResult()

        # Changes are retrieved from database and grouped by their codebase
        dl = []
        for changeid in changeids:
            dcall = getChange(changeid = changeid)
            dcall.addCallback(groupChange)
            dl.append(dcall)
        d = defer.gatherResults(dl)
        wfd = defer.waitForDeferred(d)
        yield wfd

        #process all unchanged codebases
        if self.codebases is not None:
            dl = []
            for codebase in self.codebases.iterkeys():
                if codebase not in chDict:
                    # codebase has no changes
                    # create a sourcestamp that has no changes
                    dcall = create_sourcestamp_without_changes(setid, codebase)
                    dl.append(dcall)
            d = defer.gatherResults(dl)
            wfd = defer.waitForDeferred(d)
            yield wfd                 
                 
        # process all changed codebases
        dl = []
        for codebase in chDict:
            # collect the changeids
            ids = get_changeids_from_codebase(codebase)
            lastChange = get_last_change_for_codebase(codebase)
            # pass the last change to fill the sourcestamp 
            dcall = create_sourcestamp( changeids = ids, change=lastChange, 
                                    setid = setid)
            dl.append(dcall)
        d = defer.gatherResults(dl)
        wfd = defer.waitForDeferred(d)
        yield wfd                 

        # add one buildset, this buildset is connected to the sourcestamps by the setid
        wfd = defer.waitForDeferred(self.addBuildsetForSourceStamp( setid=setid, 
                            reason=reason, external_idstring=external_idstring,
                            builderNames=builderNames, properties=properties))

        yield wfd
        yield wfd.getResult()

    @defer.deferredGenerator
    def addBuildsetForSourceStamp(self, ssid=None, setid=None, reason='', external_idstring=None,
            properties=None, builderNames=None):
        """
        Add a buildset for the given, already-existing sourcestamp.

        This method will add any properties provided to the scheduler
        constructor to the buildset, and will call the master's
        L{BuildMaster.addBuildset} method with the appropriate parameters, and
        return the same result.

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
        assert (ssid is None and setid is not None) \
            or (ssid is not None and setid is None), "pass a single sourcestamp OR set not both"

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

        if setid == None:
            if ssid != None:
                wfd = defer.waitForDeferred(self.master.db.sourcestamps.getSourceStamp(ssid))
                yield wfd
                ssdict = wfd.getResult()
                setid = ssdict['sourcestampsetid']
            else:
                # no sourcestamp and no sets
                yield None

        wfd = defer.waitForDeferred(self.master.addBuildset(
                                        sourcestampsetid=setid, reason=reason,
                                        properties=properties_dict,
                                        builderNames=builderNames,
                                        external_idstring=external_idstring))
        yield wfd
        yield wfd.getResult()
