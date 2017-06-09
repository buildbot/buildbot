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

"""Interface documentation.

Define the interfaces that are implemented by various buildbot classes.
"""

# disable pylint warnings triggered by interface definitions
# pylint: disable=no-self-argument
# pylint: disable=no-method-argument
# pylint: disable=inherit-non-class

from __future__ import absolute_import
from __future__ import print_function

from zope.interface import Attribute
from zope.interface import Interface

from buildbot.worker_transition import deprecatedWorkerModuleAttribute

# exceptions that can be raised while trying to start a build


# This class is deprecated and should no longer be used.
class NoSlaveError(Exception):
    pass


deprecatedWorkerModuleAttribute(locals(), NoSlaveError,
                                compat_name="NoSlaveError",
                                new_name="")


class BuilderInUseError(Exception):
    pass


class WorkerTooOldError(Exception):
    pass


deprecatedWorkerModuleAttribute(
    locals(), WorkerTooOldError, compat_name="BuildSlaveTooOldError")


class LatentWorkerFailedToSubstantiate(Exception):
    pass


deprecatedWorkerModuleAttribute(
    locals(), LatentWorkerFailedToSubstantiate,
    compat_name="LatentBuildSlaveFailedToSubstantiate")


class LatentWorkerSubstantiatiationCancelled(Exception):
    pass


class IPlugin(Interface):

    """
    Base interface for all Buildbot plugins
    """


class IChangeSource(IPlugin):

    """
    Service which feeds Change objects to the changemaster. When files or
    directories are changed in version control, this object should represent
    the changes as a change dictionary and call::

      self.master.addChange(who=.., rev=.., ..)

    See 'Writing Change Sources' in the manual for more information.
    """
    master = Attribute('master',
                       'Pointer to BuildMaster, automatically set when started.')

    def describe():
        """Return a string which briefly describes this source."""


class ISourceStamp(Interface):

    """
    @cvar branch: branch from which source was drawn
    @type branch: string or None

    @cvar revision: revision of the source, or None to use CHANGES
    @type revision: varies depending on VC

    @cvar patch: patch applied to the source, or None if no patch
    @type patch: None or tuple (level diff)

    @cvar changes: the source step should check out the latest revision
                   in the given changes
    @type changes: tuple of L{buildbot.changes.changes.Change} instances,
                   all of which are on the same branch

    @cvar project: project this source code represents
    @type project: string

    @cvar repository: repository from which source was drawn
    @type repository: string
    """

    def canBeMergedWith(self, other):
        """
        Can this SourceStamp be merged with OTHER?
        """

    def mergeWith(self, others):
        """Generate a SourceStamp for the merger of me and all the other
        SourceStamps. This is called by a Build when it starts, to figure
        out what its sourceStamp should be."""

    def getAbsoluteSourceStamp(self, got_revision):
        """Get a new SourceStamp object reflecting the actual revision found
        by a Source step."""

    def getText(self):
        """Returns a list of strings to describe the stamp. These are
        intended to be displayed in a narrow column. If more space is
        available, the caller should join them together with spaces before
        presenting them to the user."""


class IEmailSender(Interface):

    """I know how to send email, and can be used by other parts of the
    Buildbot to contact developers."""
    pass


class IEmailLookup(Interface):

    def getAddress(user):
        """Turn a User-name string into a valid email address. Either return
        a string (with an @ in it), None (to indicate that the user cannot
        be reached by email), or a Deferred which will fire with the same."""


class ILogObserver(Interface):

    """Objects which provide this interface can be used in a BuildStep to
    watch the output of a LogFile and parse it incrementally.
    """

    # internal methods
    def setStep(step):
        pass

    def setLog(log):
        pass

    # methods called by the LogFile
    def logChunk(build, step, log, channel, text):
        pass


class IWorker(IPlugin):
    # callback methods from the manager
    pass


deprecatedWorkerModuleAttribute(locals(), IWorker, compat_name="IBuildSlave")


class ILatentWorker(IWorker):

    """A worker that is not always running, but can run when requested.
    """
    substantiated = Attribute('Substantiated',
                              'Whether the latent worker is currently '
                              'substantiated with a real instance.')

    def substantiate():
        """Request that the worker substantiate with a real instance.

        Returns a deferred that will callback when a real instance has
        attached."""

    # there is an insubstantiate too, but that is not used externally ATM.

    def buildStarted(wfb):
        """Inform the latent worker that a build has started.

        @param wfb: a L{LatentWorkerForBuilder}.  The wfb is the one for whom the
        build finished.
        """

    def buildFinished(wfb):
        """Inform the latent worker that a build has finished.

        @param wfb: a L{LatentWorkerForBuilder}.  The wfb is the one for whom the
        build finished.
        """


deprecatedWorkerModuleAttribute(
    locals(), ILatentWorker, compat_name="ILatentBuildSlave")


class IRenderable(Interface):

    """An object that can be interpolated with properties from a build.
    """

    def getRenderingFor(iprops):
        """Return a deferred that fires with interpolation with the given properties

        @param iprops: the L{IProperties} provider supplying the properties.
        """


class IProperties(Interface):

    """
    An object providing access to build properties
    """

    def getProperty(name, default=None):
        """Get the named property, returning the default if the property does
        not exist.

        @param name: property name
        @type name: string

        @param default: default value (default: @code{None})

        @returns: property value
        """

    def hasProperty(name):
        """Return true if the named property exists.

        @param name: property name
        @type name: string
        @returns: boolean
        """

    def has_key(name):
        """Deprecated name for L{hasProperty}."""

    def setProperty(name, value, source, runtime=False):
        """Set the given property, overwriting any existing value.  The source
        describes the source of the value for human interpretation.

        @param name: property name
        @type name: string

        @param value: property value
        @type value: JSON-able value

        @param source: property source
        @type source: string

        @param runtime: (optional) whether this property was set during the
        build's runtime: usually left at its default value
        @type runtime: boolean
        """

    def getProperties():
        """Get the L{buildbot.process.properties.Properties} instance storing
        these properties.  Note that the interface for this class is not
        stable, so where possible the other methods of this interface should be
        used.

        @returns: L{buildbot.process.properties.Properties} instance
        """

    def getBuild():
        """Get the L{buildbot.process.build.Build} instance for the current
        build.  Note that this object is not available after the build is
        complete, at which point this method will return None.

        Try to avoid using this method, as the API of L{Build} instances is not
        well-defined.

        @returns L{buildbot.process.build.Build} instance
        """

    def render(value):
        """Render @code{value} as an L{IRenderable}.  This essentially coerces
        @code{value} to an L{IRenderable} and calls its @L{getRenderingFor}
        method.

        @name value: value to render
        @returns: rendered value
        """


class IScheduler(IPlugin):
    pass


class ITriggerableScheduler(Interface):

    """
    A scheduler that can be triggered by buildsteps.
    """

    def trigger(waited_for, sourcestamps=None, set_props=None,
                parent_buildid=None, parent_relationship=None):
        """Trigger a build with the given source stamp and properties.
        """


class IBuildStepFactory(Interface):

    def buildStep():
        pass


class IBuildStep(IPlugin):

    """
    A build step
    """
    # Currently has nothing


class IConfigured(Interface):

    def getConfigDict():
        pass


# #################### Deprecated Status Interfaces   ####################


class IStatus(Interface):

    """I am an object, obtainable from the buildmaster, which can provide
    status information."""

    def getTitle():
        """Return the name of the project that this Buildbot is working
        for."""

    def getTitleURL():
        """Return the URL of this Buildbot's project."""

    def getBuildbotURL():
        """Return the URL of the top-most Buildbot status page, or None if
        this Buildbot does not provide a web status page."""

    def getURLForThing(thing):
        """Return the URL of a page which provides information on 'thing',
        which should be an object that implements one of the status
        interfaces defined in L{buildbot.interfaces}. Returns None if no
        suitable page is available (or if no Waterfall is running)."""

    def getChangeSources():
        """Return a list of IChangeSource objects."""

    def getChange(number):
        """Return an IChange object."""

    def getSchedulers():
        """Return a list of ISchedulerStatus objects for all
        currently-registered Schedulers."""

    def getBuilderNames(tags=None):
        """Return a list of the names of all current Builders."""

    def getBuilder(name):
        """Return the IBuilderStatus object for a given named Builder. Raises
        KeyError if there is no Builder by that name."""

    def getWorkerNames():
        """Return a list of worker names, suitable for passing to
        getWorker()."""

    def getWorker(name):
        """Return the IWorkerStatus object for a given named worker."""

    def getBuildSets():
        """
        Return a list of un-completed build sets.

        @returns: list of L{IBuildSetStatus} implementations, via Deferred.
        """

    def generateFinishedBuilds(builders=[], branches=[],
                               num_builds=None, finished_before=None,
                               max_search=200):
        """Return a generator that will produce IBuildStatus objects each
        time you invoke its .next() method, starting with the most recent
        finished build and working backwards.

        @param builders: this is a list of Builder names, and the generator
                         will only produce builds that ran on the given
                         Builders. If the list is empty, produce builds from
                         all Builders.

        @param branches: this is a list of branch names, and the generator
                         will only produce builds that used the given
                         branches. If the list is empty, produce builds from
                         all branches.

        @param num_builds: the generator will stop after providing this many
                           builds. The default of None means to produce as
                           many builds as possible.

        @type finished_before: int: a timestamp, seconds since the epoch
        @param finished_before: if provided, do not produce any builds that
                                finished after the given timestamp.

        @type max_search: int
        @param max_search: this method may have to examine a lot of builds
                           to find some that match the search parameters,
                           especially if there aren't any matching builds.
                           This argument imposes a hard limit on the number
                           of builds that will be examined within any given
                           Builder.
        """

    def subscribe(receiver):
        """Register an IStatusReceiver to receive new status events. The
        receiver will immediately be sent a set of 'builderAdded' messages
        for all current builders. It will receive further 'builderAdded' and
        'builderRemoved' messages as the config file is reloaded and builders
        come and go. It will also receive 'buildsetSubmitted' messages for
        all outstanding BuildSets (and each new BuildSet that gets
        submitted). No additional messages will be sent unless the receiver
        asks for them by calling .subscribe on the IBuilderStatus objects
        which accompany the addedBuilder message."""

    def unsubscribe(receiver):
        """Unregister an IStatusReceiver. No further status messages will be
        delivered."""


class IBuildSetStatus(Interface):

    """I represent a set of Builds, each run on a separate Builder but all
    using the same source tree."""

    def getReason():
        pass

    def getID():
        """Return the BuildSet's ID string, if any. The 'try' feature uses a
        random string as a BuildSetID to relate submitted jobs with the
        resulting BuildSet."""

    def getResponsibleUsers():
        pass  # not implemented

    def getInterestedUsers():
        pass  # not implemented

    def getBuilderNames():
        """Return a list of the names of all Builders on which this set will
        do builds.

        @returns: list of names via Deferred"""

    def isFinished():
        pass

    def waitUntilFinished():
        """Return a Deferred that fires (with this IBuildSetStatus object)
        when all builds have finished."""

    def getResults():
        """Return SUCCESS/FAILURE, or None if the buildset is not finished
        yet"""


class IBuildRequestStatus(Interface):

    """I represent a request to build a particular set of source code on a
    particular Builder. These requests may be merged by the time they are
    finally turned into a Build."""

    def getSourceStamp():
        """
        Get a SourceStamp object which can be used to re-create the source tree
        that this build used.  This method will return an absolute SourceStamp
        if possible, and its results may change as the build progresses.
        Specifically, a "HEAD" build may later be more accurately specified by
        an absolute SourceStamp with the specific revision information.

        This method will return None if the source information is no longer
        available.

        @returns: SourceStamp via Deferred
        """

    def getBuilds():
        """Return a list of IBuildStatus objects for each Build that has been
        started in an attempt to satisfy this BuildRequest."""

    def subscribe(observer):
        """Register a callable that will be invoked (with a single
        IBuildStatus object) for each Build that is created to satisfy this
        request. There may be multiple Builds created in an attempt to handle
        the request: they may be interrupted by the user or abandoned due to
        a lost worker. The last Build (the one which actually gets to run to
        completion) is said to 'satisfy' the BuildRequest. The observer will
        be called once for each of these Builds, both old and new."""

    def unsubscribe(observer):
        """Unregister the callable that was registered with subscribe()."""

    def getSubmitTime():
        """Return the time when this request was submitted.  Returns a
        Deferred."""


class IWorkerStatus(Interface):

    def getName():
        """Return the name of the worker."""

    def getAdmin():
        """Return a string with the worker admin's contact data."""

    def getHost():
        """Return a string with the worker host info."""

    def isConnected():
        """Return True if the worker is currently online, False if not."""

    def lastMessageReceived():
        """Return a timestamp (seconds since epoch) indicating when the most
        recent message was received from the worker."""


deprecatedWorkerModuleAttribute(locals(), IWorkerStatus)


class ISchedulerStatus(Interface):

    def getName():
        """Return the name of this Scheduler (a string)."""

    def getPendingBuildsets():
        """Return an IBuildSet for all BuildSets that are pending. These
        BuildSets are waiting for their tree-stable-timers to expire."""
        # TODO: this is not implemented anywhere


class IBuilderStatus(Interface):

    def getName():
        """Return the name of this Builder (a string)."""

    def getDescription():
        """Return the description of this builder (a string)."""

    def getState():
        # TODO: this isn't nearly as meaningful as it used to be
        """Return a tuple (state, builds) for this Builder. 'state' is the
        so-called 'big-status', indicating overall status (as opposed to
        which step is currently running). It is a string, one of 'offline',
        'idle', or 'building'. 'builds' is a list of IBuildStatus objects
        (possibly empty) representing the currently active builds."""

    def getWorkers():
        """Return a list of IWorkerStatus objects for the workers that are
        used by this builder."""

    def getPendingBuildRequestStatuses():
        """
        Get a L{IBuildRequestStatus} implementations for all unclaimed build
        requests.

        @returns: list of objects via Deferred
        """

    def getCurrentBuilds():
        """Return a list containing an IBuildStatus object for each build
        currently in progress."""
        # again, we could probably provide an object for 'waiting' and
        # 'interlocked' too, but things like the Change list might still be
        # subject to change

    def getLastFinishedBuild():
        """Return the IBuildStatus object representing the last finished
        build, which may be None if the builder has not yet finished any
        builds."""

    def getBuild(number):
        """Return an IBuildStatus object for a historical build. Each build
        is numbered (starting at 0 when the Builder is first added),
        getBuild(n) will retrieve the Nth such build. getBuild(-n) will
        retrieve a recent build, with -1 being the most recent build
        started. If the Builder is idle, this will be the same as
        getLastFinishedBuild(). If the Builder is active, it will be an
        unfinished build. This method will return None if the build is no
        longer available. Older builds are likely to have less information
        stored: Logs are the first to go, then Steps."""

    def getEvent(number):
        """Return an IStatusEvent object for a recent Event. Builders
        connecting and disconnecting are events, as are ping attempts.
        getEvent(-1) will return the most recent event. Events are numbered,
        but it probably doesn't make sense to ever do getEvent(+n)."""

    def generateFinishedBuilds(branches=[],
                               num_builds=None,
                               max_buildnum=None, finished_before=None,
                               max_search=200,
                               ):
        """Return a generator that will produce IBuildStatus objects each
        time you invoke its .next() method, starting with the most recent
        finished build, then the previous build, and so on back to the oldest
        build available.

        @param branches: this is a list of branch names, and the generator
                         will only produce builds that involve the given
                         branches. If the list is empty, the generator will
                         produce all builds regardless of what branch they
                         used.

        @param num_builds: if provided, the generator will stop after
                           providing this many builds. The default of None
                           means to produce as many builds as possible.

        @param max_buildnum: if provided, the generator will start by
                             providing the build with this number, or the
                             highest-numbered preceding build (i.e. the
                             generator will not produce any build numbered
                             *higher* than max_buildnum). The default of None
                             means to start with the most recent finished
                             build. -1 means the same as None. -2 means to
                             start with the next-most-recent completed build,
                             etc.

        @type finished_before: int: a timestamp, seconds since the epoch
        @param finished_before: if provided, do not produce any builds that
                                finished after the given timestamp.

        @type max_search: int
        @param max_search: this method may have to examine a lot of builds
                           to find some that match the search parameters,
                           especially if there aren't any matching builds.
                           This argument imposes a hard limit on the number
                           of builds that will be examined.
        """

    def subscribe(receiver):
        """Register an IStatusReceiver to receive new status events. The
        receiver will be given builderChangedState, buildStarted, and
        buildFinished messages."""

    def unsubscribe(receiver):
        """Unregister an IStatusReceiver. No further status messages will be
        delivered."""


class IEventSource(Interface):

    def eventGenerator(branches=[], categories=[], committers=[], projects=[], minTime=0):
        """This function creates a generator which will yield all of this
        object's status events, starting with the most recent and progressing
        backwards in time. These events provide the IStatusEvent interface.
        At the moment they are all instances of buildbot.status.builder.Event
        or buildbot.status.builder.BuildStepStatus .

        @param branches: a list of branch names. The generator should only
        return events that are associated with these branches. If the list is
        empty, events for all branches should be returned (i.e. an empty list
        means 'accept all' rather than 'accept none').

        @param categories: a list of category names.  The generator
        should only return events that are categorized within the
        given category.  If the list is empty, events for all
        categories should be returned.

        @param comitters: a list of committers.  The generator should only
        return events caused by one of the listed committers. If the list is
        empty or None, events from every committers should be returned.

        @param minTime: a timestamp. Do not generate events occurring prior to
        this timestamp.
        """


class IBuildStatus(Interface):

    """I represent the status of a single Build/BuildRequest. It could be
    in-progress or finished."""

    def getBuilder():
        """
        Return the BuilderStatus that owns this build.

        @rtype: implementer of L{IBuilderStatus}
        """

    def isFinished():
        """Return a boolean. True means the build has finished, False means
        it is still running."""

    def waitUntilFinished():
        """Return a Deferred that will fire when the build finishes. If the
        build has already finished, this deferred will fire right away. The
        callback is given this IBuildStatus instance as an argument."""

    def getReason():
        """Return a string that indicates why the build was run. 'changes',
        'forced', and 'periodic' are the most likely values. 'try' will be
        added in the future."""

    def getChanges():
        """Return a list of Change objects which represent which source
        changes went into the build."""

    def getRevisions():
        """Returns a string representing the list of revisions that led to
        the build, rendered from each Change.revision"""

    def getResponsibleUsers():
        """Return a list of Users who are to blame for the changes that went
        into this build. If anything breaks (at least anything that wasn't
        already broken), blame them. Specifically, this is the set of users
        who were responsible for the Changes that went into this build. Each
        User is a string, corresponding to their name as known by the VC
        repository."""

    def getInterestedUsers():
        """Return a list of Users who will want to know about the results of
        this build but who did not actually make the Changes that went into it
        (build sheriffs, code-domain owners)."""

    def getNumber():
        """Within each builder, each Build has a number. Return it."""

    def getPreviousBuild():
        """Convenience method. Returns None if the previous build is
        unavailable."""

    def getSteps():
        """Return a list of IBuildStepStatus objects. For invariant builds
        (those which always use the same set of Steps), this should always
        return the complete list, however some of the steps may not have
        started yet (step.getTimes()[0] will be None). For variant builds,
        this may not be complete (asking again later may give you more of
        them)."""

    def getTimes():
        """Returns a tuple of (start, end). 'start' and 'end' are the times
        (seconds since the epoch) when the Build started and finished. If
        the build is still running, 'end' will be None."""

    # while the build is running, the following methods make sense.
    # Afterwards they return None

    def getCurrentStep():
        """Return an IBuildStepStatus object representing the currently
        active step."""

    # Once you know the build has finished, the following methods are legal.
    # Before ths build has finished, they all return None.

    def getWorkername():
        """Return the name of the worker which handled this build."""

    def getText():
        """Returns a list of strings to describe the build. These are
        intended to be displayed in a narrow column. If more space is
        available, the caller should join them together with spaces before
        presenting them to the user."""

    def getResults():
        """Return a constant describing the results of the build: one of the
        constants in buildbot.status.builder: SUCCESS, WARNINGS,
        FAILURE, SKIPPED or EXCEPTION."""

    def getLogs():
        """Return a list of logs that describe the build as a whole. Some
        steps will contribute their logs, while others are are less important
        and will only be accessible through the IBuildStepStatus objects.
        Each log is an object which implements the IStatusLog interface."""

    def getTestResults():
        """Return a dictionary that maps test-name tuples to ITestResult
        objects. This may return an empty or partially-filled dictionary
        until the build has completed."""

    # subscription interface

    def subscribe(receiver, updateInterval=None):
        """Register an IStatusReceiver to receive new status events. The
        receiver will be given stepStarted and stepFinished messages. If
        'updateInterval' is non-None, buildETAUpdate messages will be sent
        every 'updateInterval' seconds."""

    def unsubscribe(receiver):
        """Unregister an IStatusReceiver. No further status messages will be
        delivered."""


class IStatusEvent(Interface):

    """I represent a Builder Event, something non-Build related that can
    happen to a Builder."""

    def getTimes():
        """Returns a tuple of (start, end) like IBuildStepStatus, but end==0
        indicates that this is a 'point event', which has no duration.
        WorkerConnect/Disconnect are point events. Ping is not: it starts
        when requested and ends when the response (positive or negative) is
        returned"""

    def getText():
        """Returns a list of strings which describe the event. These are
        intended to be displayed in a narrow column. If more space is
        available, the caller should join them together with spaces before
        presenting them to the user."""


class IStatusLogConsumer(Interface):

    """I am an object which can be passed to IStatusLog.subscribeConsumer().
    I represent a target for writing the contents of an IStatusLog. This
    differs from a regular IStatusReceiver in that it can pause the producer.
    This makes it more suitable for use in streaming data over network
    sockets, such as an HTTP request. Note that the consumer can only pause
    the producer until it has caught up with all the old data. After that
    point, C{pauseProducing} is ignored and all new output from the log is
    sent directory to the consumer."""

    def registerProducer(producer, streaming):
        """A producer is being hooked up to this consumer. The consumer only
        has to handle a single producer. It should send .pauseProducing and
        .resumeProducing messages to the producer when it wants to stop or
        resume the flow of data. 'streaming' will be set to True because the
        producer is always a PushProducer.
        """

    def unregisterProducer():
        """The previously-registered producer has been removed. No further
        pauseProducing or resumeProducing calls should be made. The consumer
        should delete its reference to the Producer so it can be released."""

    def writeChunk(chunk):
        """A chunk (i.e. a tuple of (channel, text)) is being written to the
        consumer."""

    def finish():
        """The log has finished sending chunks to the consumer."""


class IStatusReceiver(IPlugin):

    """I am an object which can receive build status updates. I may be
    subscribed to an IStatus, an IBuilderStatus, or an IBuildStatus."""

    def buildsetSubmitted(buildset):
        """A new BuildSet has been submitted to the buildmaster.

        @type buildset: implementer of L{IBuildSetStatus}
        """

    def requestSubmitted(request):
        """A new BuildRequest has been submitted to the buildmaster.

        @type request: implementer of L{IBuildRequestStatus}
        """

    def requestCancelled(builder, request):
        """A BuildRequest has been cancelled on the given Builder.

        @type builder: L{buildbot.status.builder.BuilderStatus}
        @type request: implementer of L{IBuildRequestStatus}
        """

    def builderAdded(builderName, builder):
        """
        A new Builder has just been added. This method may return an
        IStatusReceiver (probably 'self') which will be subscribed to receive
        builderChangedState and buildStarted/Finished events.

        @type  builderName: string
        @type  builder:     L{buildbot.status.builder.BuilderStatus}
        @rtype: implementer of L{IStatusReceiver}
        """

    def builderChangedState(builderName, state):
        """Builder 'builderName' has changed state. The possible values for
        'state' are 'offline', 'idle', and 'building'."""

    def buildStarted(builderName, build):
        """Builder 'builderName' has just started a build. The build is an
        object which implements IBuildStatus, and can be queried for more
        information.

        This method may return an IStatusReceiver (it could even return
        'self'). If it does so, stepStarted and stepFinished methods will be
        invoked on the object for the steps of this one build. This is a
        convenient way to subscribe to all build steps without missing any.
        This receiver will automatically be unsubscribed when the build
        finishes.

        It can also return a tuple of (IStatusReceiver, interval), in which
        case buildETAUpdate messages are sent ever 'interval' seconds, in
        addition to the stepStarted and stepFinished messages."""

    def buildETAUpdate(build, ETA):
        """This is a periodic update on the progress this Build has made
        towards completion."""

    def changeAdded(change):
        """A new Change was added to the ChangeMaster.  By the time this event
        is received, all schedulers have already received the change."""

    def stepStarted(build, step):
        """A step has just started. 'step' is the IBuildStepStatus which
        represents the step: it can be queried for more information.

        This method may return an IStatusReceiver (it could even return
        'self'). If it does so, logStarted and logFinished methods will be
        invoked on the object for logs created by this one step. This
        receiver will be automatically unsubscribed when the step finishes.

        Alternatively, the method may return a tuple of an IStatusReceiver
        and an integer named 'updateInterval'. In addition to
        logStarted/logFinished messages, it will also receive stepETAUpdate
        messages about every updateInterval seconds."""

    def stepTextChanged(build, step, text):
        """The text for a step has been updated.

        This is called when calling setText() on the step status, and
        hands in the text list."""

    def stepText2Changed(build, step, text2):
        """The text2 for a step has been updated.

        This is called when calling setText2() on the step status, and
        hands in text2 list."""

    def stepETAUpdate(build, step, ETA, expectations):
        """This is a periodic update on the progress this Step has made
        towards completion. It gets an ETA (in seconds from the present) of
        when the step ought to be complete, and a list of expectation tuples
        (as returned by IBuildStepStatus.getExpectations) with more detailed
        information."""

    def logStarted(build, step, log):
        """A new Log has been started, probably because a step has just
        started running a shell command. 'log' is the IStatusLog object
        which can be queried for more information.

        This method may return an IStatusReceiver (such as 'self'), in which
        case the target's logChunk method will be invoked as text is added to
        the logfile. This receiver will automatically be unsubsribed when the
        log finishes."""

    def logChunk(build, step, log, channel, text):
        """Some text has been added to this log. 'channel' is one of
        LOG_CHANNEL_STDOUT, LOG_CHANNEL_STDERR, or LOG_CHANNEL_HEADER, as
        defined in IStatusLog.getChunks."""

    def logFinished(build, step, log):
        """A Log has been closed."""

    def stepFinished(build, step, results):
        """A step has just finished. 'results' is the result tuple described
        in IBuildStepStatus.getResults."""

    def buildFinished(builderName, build, results):
        """
        A build has just finished. 'results' is the result tuple described
        in L{IBuildStatus.getResults}.

        @type  builderName: string
        @type  build:       L{buildbot.status.build.BuildStatus}
        @type  results:     tuple
        """

    def builderRemoved(builderName):
        """The Builder has been removed."""

    def workerConnected(workerName):
        """The worker has connected."""

    def workerDisconnected(workerName):
        """The worker has disconnected."""

    def checkConfig(otherStatusReceivers):
        """Verify that there are no other status receivers which conflict with
        the current one.

        @type  otherStatusReceivers: A list of L{IStatusReceiver} objects which
        will contain self.
        """


class IControl(Interface):

    def addChange(change):
        """Add a change to the change queue, for analysis by schedulers."""

    def getBuilder(name):
        """Retrieve the IBuilderControl object for the given Builder."""


class IBuilderControl(Interface):

    def rebuildBuild(buildStatus, reason="<rebuild, no reason given>"):
        """Rebuild something we've already built before. This submits a
        BuildRequest to our Builder using the same SourceStamp as the earlier
        build. This has no effect (but may eventually raise an exception) if
        this Build has not yet finished."""

    def getPendingBuildRequestControls():
        """
        Get a list of L{IBuildRequestControl} objects for this Builder.
        Each one corresponds to an unclaimed build request.

        @returns: list of objects via Deferred
        """

    def getBuild(number):
        """Attempt to return an IBuildControl object for the given build.
        Returns None if no such object is available. This will only work for
        the build that is currently in progress: once the build finishes,
        there is nothing to control anymore."""

    def ping():
        """Attempt to contact the worker and see if it is still alive. This
        returns a Deferred which fires with either True (the worker is still
        alive) or False (the worker did not respond). As a side effect, adds an
        event to this builder's column in the waterfall display containing the
        results of the ping. Note that this may not fail for a long time, it is
        implemented in terms of the timeout on the underlying TCP connection."""


class IBuildRequestControl(Interface):

    def subscribe(observer):
        """Register a callable that will be invoked (with a single
        IBuildControl object) for each Build that is created to satisfy this
        request. There may be multiple Builds created in an attempt to handle
        the request: they may be interrupted by the user or abandoned due to
        a lost worker. The last Build (the one which actually gets to run to
        completion) is said to 'satisfy' the BuildRequest. The observer will
        be called once for each of these Builds, both old and new."""
    def unsubscribe(observer):
        """Unregister the callable that was registered with subscribe()."""
    def cancel():
        """Remove the build from the pending queue. Has no effect if the
        build has already been started."""


class IBuildControl(Interface):

    def getStatus():
        """Return an IBuildStatus object for the Build that I control."""
    def stopBuild(reason="<no reason given>"):
        """Halt the build. This has no effect if the build has already
        finished."""


class IConfigLoader(Interface):

    def loadConfig():
        """
        Load the specified configuration.

        :return MasterConfig:
        """


class IHttpResponse(Interface):

    def content():
        """
        :returns: raw (``bytes``) content of the response via deferred
        """
    def json():
        """
        :returns: json decoded content of the response via deferred
        """
    master = Attribute('code',
                       "http status code of the request's response (e.g 200)")


class IConfigurator(Interface):

    def configure(config_dict):
        """
        Alter the buildbot config_dict, as defined in master.cfg

        like the master.cfg, this is run out of the main reactor thread, so this can block, but this can't
        call most Buildbot facilities.

        :returns: None
        """
