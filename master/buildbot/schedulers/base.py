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
from buildbot import config, interfaces
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
        self._change_subscription = None
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

        # register for changes with master
        assert not self._change_subscription
        def changeCallback(change):
            # ignore changes delivered while we're not running
            if not self._change_subscription:
                return

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
        self._change_subscription = self.master.subscribeToChanges(changeCallback)

        return defer.succeed(None)

    def _stopConsumingChanges(self):
        # (note: called automatically in stopService)

        # acquire the lock change consumption lock to ensure that any change
        # consumption is complete before we are done stopping consumption
        def stop():
            if self._change_subscription:
                self._change_subscription.unsubscribe()
                self._change_subscription = None
        return self._change_consumption_lock.run(stop)

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

    @defer.inlineCallbacks
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
        setid = yield self.master.db.sourcestampsets.addSourceStampSet()

        # add a sourcestamp for each codebase
        for codebase, cb_info in self.codebases.iteritems():
            ss_repository = cb_info.get('repository', repository)
            ss_branch = cb_info.get('branch', branch)
            ss_revision = cb_info.get('revision', None)
            yield self.master.db.sourcestamps.addSourceStamp(
                        codebase=codebase,
                        repository=ss_repository,
                        branch=ss_branch,
                        revision=ss_revision,
                        project=project,
                        changeids=set(),
                        sourcestampsetid=setid)

        bsid,brids = yield self.addBuildsetForSourceStamp(
                                setid=setid, reason=reason,
                                external_idstring=external_idstring,
                                builderNames=builderNames,
                                properties=properties)

        defer.returnValue((bsid,brids))


    @defer.inlineCallbacks
    def addBuildsetForSourceStampDetails(self, reason='', external_idstring=None,
                        branch=None, repository='', project='', revision=None,
                        builderNames=None, properties=None):
        """
        Given details about the source code to build, create a source stamp and
        then add a buildset for it.

        @param reason: reason for this buildset
        @type reason: unicode string
        @param external_idstring: external identifier for this buildset, or None
        @param branch: branch to build (note that None often has a special meaning)
        @param repository: repository name for sourcestamp
        @param project: project name for sourcestamp
        @param revision: revision to build - default is latest
        @param builderNames: builders to name in the buildset (defaults to
            C{self.builderNames})
        @param properties: a properties object containing initial properties for
            the buildset
        @type properties: L{buildbot.process.properties.Properties}
        @returns: (buildset ID, buildrequest IDs) via Deferred
        """
        # Define setid for this set of changed repositories
        setid = yield self.master.db.sourcestampsets.addSourceStampSet()

        yield self.master.db.sourcestamps.addSourceStamp(
                branch=branch, revision=revision, repository=repository,
                project=project, sourcestampsetid=setid)

        rv = yield self.addBuildsetForSourceStamp(
                                setid=setid, reason=reason,
                                external_idstring=external_idstring,
                                builderNames=builderNames,
                                properties=properties)
        defer.returnValue(rv)


    @defer.inlineCallbacks
    def addBuildsetForSourceStampSetDetails(self, reason, sourcestamps,
                                            properties, builderNames=None):
        if sourcestamps is None:
            sourcestamps = {}

        # Define new setid for this set of sourcestamps
        new_setid = yield self.master.db.sourcestampsets.addSourceStampSet()

        # Merge codebases with the passed list of sourcestamps
        # This results in a new sourcestamp for each codebase
        for codebase in self.codebases:
            ss = self.codebases[codebase].copy()
             # apply info from passed sourcestamps onto the configured default
             # sourcestamp attributes for this codebase.
            ss.update(sourcestamps.get(codebase,{}))

            # add sourcestamp to the new setid
            yield self.master.db.sourcestamps.addSourceStamp(
                        codebase=codebase,
                        repository=ss.get('repository', None),
                        branch=ss.get('branch', None),
                        revision=ss.get('revision', None),
                        project=ss.get('project', ''),
                        changeids=[c['number'] for c in ss.get('changes', [])],
                        patch_body=ss.get('patch_body', None),
                        patch_level=ss.get('patch_level', None),
                        patch_author=ss.get('patch_author', None),
                        patch_comment=ss.get('patch_comment', None),
                        sourcestampsetid=new_setid)

        rv = yield self.addBuildsetForSourceStamp(
                                setid=new_setid, reason=reason,
                                properties=properties,
                                builderNames=builderNames)

        defer.returnValue(rv)


    @defer.inlineCallbacks
    def addBuildsetForChanges(self, reason='', external_idstring=None,
            changeids=[], builderNames=None, properties=None):
        changesByCodebase = {}

        def get_last_change_for_codebase(codebase):
            return max(changesByCodebase[codebase],key = lambda change: change["changeid"])

        # Define setid for this set of changed repositories
        setid = yield self.master.db.sourcestampsets.addSourceStampSet()

        # Changes are retrieved from database and grouped by their codebase
        for changeid in changeids:
            chdict = yield self.master.db.changes.getChange(changeid)
            # group change by codebase
            changesByCodebase.setdefault(chdict["codebase"], []).append(chdict)

        for codebase in self.codebases:
            args = {'codebase': codebase, 'sourcestampsetid': setid }
            if codebase not in changesByCodebase:
                # codebase has no changes
                # create a sourcestamp that has no changes
                args['repository'] = self.codebases[codebase]['repository']
                args['branch'] = self.codebases[codebase].get('branch', None)
                args['revision'] = self.codebases[codebase].get('revision', None)
                args['changeids'] = set()
                args['project'] = ''
            else:
                #codebase has changes
                args['changeids'] = [c["changeid"] for c in changesByCodebase[codebase]]
                lastChange = get_last_change_for_codebase(codebase)
                for key in ['repository', 'branch', 'revision', 'project']:
                    args[key] = lastChange[key]

            yield self.master.db.sourcestamps.addSourceStamp(**args)

        # add one buildset, this buildset is connected to the sourcestamps by the setid
        bsid,brids = yield self.addBuildsetForSourceStamp( setid=setid,
                            reason=reason, external_idstring=external_idstring,
                            builderNames=builderNames, properties=properties)

        defer.returnValue((bsid,brids))

    @defer.inlineCallbacks
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
            if ssid is not None:
                ssdict = yield self.master.db.sourcestamps.getSourceStamp(ssid)
                setid = ssdict['sourcestampsetid']
            else:
                # no sourcestamp and no sets
                yield None

        rv = yield self.master.addBuildset(sourcestampsetid=setid,
                            reason=reason, properties=properties_dict,
                            builderNames=builderNames,
                            external_idstring=external_idstring)
        defer.returnValue(rv)

