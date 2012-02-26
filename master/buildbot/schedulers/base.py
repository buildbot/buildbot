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

    compare_attrs = ('name', 'builderNames', 'properties')

    def __init__(self, name, builderNames, properties):
        """
        Initialize a Scheduler.

        @param name: name of this scheduler (used as a key for state)
        @type name: unicode

        @param builderNames: list of builders this scheduler may start
        @type builderNames: list of unicode

        @param properties: properties to add to builds triggered by this
        scheduler
        @type properties: dictionary

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
        """
        Add a buildset for the combination of the given changesets, creating
        a sourcestamp based on those changes.  The sourcestamp for the buildset
        will reference all of the indicated changes.

        This method will add any properties provided to the scheduler
        constructor to the buildset, and will call the master's addBuildset
        method with the appropriate parameters.

        @param reason: reason for this buildset
        @type reason: unicode string
        @param external_idstring: external identifier for this buildset, or None
        @param changeids: nonempty list of changes to include in this buildset
        @param builderNames: builders to name in the buildset (defaults to
            C{self.builderNames})
        @param properties: a properties object containing initial properties for
            the buildset
        @type properties: L{buildbot.process.properties.Properties}
        @returns: (buildset ID, buildrequest IDs) via Deferred
        """
        assert changeids is not []

        # attributes for this sourcestamp will be based on the most recent
        # change, so fetch the change with the highest id
        wfd = defer.waitForDeferred(self.master.db.changes.getChange(max(changeids)))
        yield wfd
        chdict = wfd.getResult()

        change = None
        if chdict:
            wfd = defer.waitForDeferred(changes.Change.fromChdict(self.master, chdict))
            yield wfd
            change = wfd.getResult()

        # Define setid for this set of changed repositories
        wfd = defer.waitForDeferred(self.master.db.sourcestampsets.addSourceStampSet())
        yield wfd
        setid = wfd.getResult()

        wfd = defer.waitForDeferred(self.master.db.sourcestamps.addSourceStamp(
                    branch=change.branch,
                    revision=change.revision,
                    repository=change.repository,
                    project=change.project,
                    changeids=changeids,
                    sourcestampsetid=setid))
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
    def addBuildsetForChangesMultiRepo(self, reason='', external_idstring=None,
            changeids=[], builderNames=None, properties=None):
        assert changeids is not []
        chDicts = {}

        def getChange(changeid = None):
            d = self.master.db.changes.getChange(changeid)
            def chdict2change(chdict):
                if not chdict:
                    return None
                return changes.Change.fromChdict(self.master, chdict)
            d.addCallback(chdict2change)

        def groupChange(change):
            if change.repository not in chDicts:
                chDicts[change.repository] = []
            chDicts[change.repository].append(change)

        def get_changeids_from_repo(repository):
            changeids = []
            for change in chDicts[repository]:
                changeids.append(change.number)
            return changeids

        def create_sourcestamp(changeids, change = None, setid = None):
            def add_sourcestamp(setid, changeids = None):
                return self.master.db.sourcestamps.addSourceStamp(
                        branch=change.branch,
                        revision=change.revision,
                        repository=change.repository,
                        project=change.project,
                        changeids=changeids,
                        setid=setid)
            d.addCallback(add_sourcestamp, setid = setid, changeids = changeids)
            return d

        def create_sourcestamp_without_changes(setid, repository):
            return self.master.db.sourcestamps.addSourceStamp(
                    branch=self.default_branch,
                    revision=None,
                    repository=repository,
                    project=self.default_project,
                    changeids=changeids,
                    sourcestampsetid=setid)

        d = defer.Deferred()
        if self.repositories is None:
            # attributes for this sourcestamp will be based on the most recent
            # change, so fetch the change with the highest id (= old single
            # sourcestamp functionality)
            d.addCallBack(getChange,changeid=max(changeids))
            d.addCallBack(groupChange)
        else:
            for changeid in changeids:
                d.addCallBack(getChange,changeid = changeid)
                d.addCallBack(groupChange)

        # Define setid for this set of changed repositories
        wfd = defer.waitForDeferred(self.master.db.sourcestampsets.addSourceStampSet)
        yield wfd
        setid = wfd.getResult()

        #process all unchanged repositories
        if self.repositories is not None:
            for repo in self.repositories:
                if repo not in chDicts:
                    # repository was not changed
                    # call create_sourcestamp
                    d.addCallback(create_sourcestamp_without_changes, setid, repo)

        # process all changed
        for repo in chDicts:
            d.addCallback(get_changeids_from_repo, repository = repo)
            d.addCallback(create_sourcestamp, setid = setid, change=chDicts[repo][-1])

        # add one buildset, this buildset is connected to the sourcestamps by the setid
        d.addCallback(self.addBuildsetForSourceStamp, setid=setid, reason=reason,
                            external_idstring=external_idstring,
                            builderNames=builderNames,
                            properties=properties)

        yield d


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
