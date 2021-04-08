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

from twisted.python.deprecate import deprecatedModuleAttribute
from twisted.python.versions import Version
from zope.interface import Attribute
from zope.interface import Interface

# exceptions that can be raised while trying to start a build


class BuilderInUseError(Exception):
    pass


class WorkerSetupError(Exception):
    pass


WorkerTooOldError = WorkerSetupError
deprecatedModuleAttribute(
    Version("buildbot", 2, 9, 0),
    message="Use WorkerSetupError instead.",
    moduleName="buildbot.interfaces",
    name="WorkerTooOldError",
)


class LatentWorkerFailedToSubstantiate(Exception):
    pass


class LatentWorkerCannotSubstantiate(Exception):
    pass


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

      self.master.data.updates.addChange(who=.., rev=.., ..)

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


class IMachine(Interface):
    pass


class IMachineAction(Interface):
    def perform(self, manager):
        """ Perform an action on the machine managed by manager. Returns a
            deferred evaluating to True if it was possible to execute the
            action.
        """


class ILatentMachine(IMachine):
    """ A machine that is not always running, but can be started when requested.
    """


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


class IReportGenerator(Interface):

    def generate(self, master, reporter, key, build):
        pass


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
    code = Attribute('code',
                     "http status code of the request's response (e.g 200)")
    url = Attribute('url',
                    "request's url (e.g https://api.github.com/endpoint')")


class IConfigurator(Interface):

    def configure(config_dict):
        """
        Alter the buildbot config_dict, as defined in master.cfg

        like the master.cfg, this is run out of the main reactor thread, so this can block, but
        this can't call most Buildbot facilities.

        :returns: None
        """
