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


import os, weakref

from zope.interface import implements
from twisted.python import log
from twisted.application import strports, service
from twisted.web import server, distrib, static
from twisted.spread import pb
from twisted.web.util import Redirect

from buildbot.interfaces import IStatusReceiver

from buildbot.status.web.base import StaticFile, createJinjaEnv
from buildbot.status.web.feeds import Rss20StatusResource, \
     Atom10StatusResource
from buildbot.status.web.waterfall import WaterfallStatusResource
from buildbot.status.web.console import ConsoleStatusResource
from buildbot.status.web.olpb import OneLinePerBuild
from buildbot.status.web.grid import GridStatusResource, TransposedGridStatusResource
from buildbot.status.web.changes import ChangesResource
from buildbot.status.web.builder import BuildersResource
from buildbot.status.web.buildstatus import BuildStatusStatusResource
from buildbot.status.web.slaves import BuildSlavesResource
from buildbot.status.web.status_json import JsonStatusResource
from buildbot.status.web.about import AboutBuildbot
from buildbot.status.web.authz import Authz
from buildbot.status.web.auth import AuthFailResource
from buildbot.status.web.root import RootPage
from buildbot.status.web.change_hook import ChangeHookResource

# this class contains the WebStatus class.  Basic utilities are in base.py,
# and specific pages are each in their own module.

class WebStatus(service.MultiService):
    implements(IStatusReceiver)
    # TODO: IStatusReceiver is really about things which subscribe to hear
    # about buildbot events. We need a different interface (perhaps a parent
    # of IStatusReceiver) for status targets that don't subscribe, like the
    # WebStatus class. buildbot.master.BuildMaster.loadConfig:737 asserts
    # that everything in c['status'] provides IStatusReceiver, but really it
    # should check that they provide IStatusTarget instead.

    """
    The webserver provided by this class has the following resources:

     /waterfall : the big time-oriented 'waterfall' display, with links
                  to individual changes, builders, builds, steps, and logs.
                  A number of query-arguments can be added to influence
                  the display.
     /rss : a rss feed summarizing all failed builds. The same
            query-arguments used by 'waterfall' can be added to
            influence the feed output.
     /atom : an atom feed summarizing all failed builds. The same
             query-arguments used by 'waterfall' can be added to
             influence the feed output.
     /grid : another summary display that shows a grid of builds, with
             sourcestamps on the x axis, and builders on the y.  Query
             arguments similar to those for the waterfall can be added.
     /tgrid : similar to the grid display, but the commits are down the
              left side, and the build hosts are across the top.
     /builders/BUILDERNAME: a page summarizing the builder. This includes
                            references to the Schedulers that feed it,
                            any builds currently in the queue, which
                            buildslaves are designated or attached, and a
                            summary of the build process it uses.
     /builders/BUILDERNAME/builds/NUM: a page describing a single Build
     /builders/BUILDERNAME/builds/NUM/steps/STEPNAME: describes a single step
     /builders/BUILDERNAME/builds/NUM/steps/STEPNAME/logs/LOGNAME: a StatusLog
     /builders/_all/{force,stop}: force a build/stop building on all builders.
     /buildstatus?builder=...&number=...: an embedded iframe for the console
     /changes : summarize all ChangeSources
     /changes/CHANGENUM: a page describing a single Change
     /buildslaves : list all BuildSlaves
     /buildslaves/SLAVENAME : describe a single BuildSlave
     /one_line_per_build : summarize the last few builds, one line each
     /one_line_per_build/BUILDERNAME : same, but only for a single builder
     /about : describe this buildmaster (Buildbot and support library versions)
     /change_hook[/DIALECT] : accepts changes from external sources, optionally
                              choosing the dialect that will be permitted
                              (i.e. github format, etc..)

     and more!  see the manual.


    All URLs for pages which are not defined here are used to look
    for files in PUBLIC_HTML, which defaults to BASEDIR/public_html.
    This means that /robots.txt or /favicon.ico can be placed in
    that directory

    This webserver uses the jinja2 template system to generate the web pages
    (see http://jinja.pocoo.org/2/) and by default loads pages from the
    buildbot.status.web.templates package. Any file here can be overridden by placing
    a corresponding file in the master's 'templates' directory.

    The main customization points are layout.html which loads style sheet
    (css) and provides header and footer content, and root.html, which
    generates the root page.

    All of the resources provided by this service use relative URLs to reach
    each other. The only absolute links are the c['titleURL'] links at the
    top and bottom of the page, and the buildbot home-page link at the
    bottom.

    Buildbot uses some generic classes to identify the type of object, and
    some more specific classes for the various kinds of those types. It does
    this by specifying both in the class attributes where applicable,
    separated by a space. It is important that in your CSS you declare the
    more generic class styles above the more specific ones. For example,
    first define a style for .Event, and below that for .SUCCESS

    The following CSS class names are used:
        - Activity, Event, BuildStep, LastBuild: general classes
        - waiting, interlocked, building, offline, idle: Activity states
        - start, running, success, failure, warnings, skipped, exception:
          LastBuild and BuildStep states
        - Change: box with change
        - Builder: box for builder name (at top)
        - Project
        - Time

    """

    # we are not a ComparableMixin, and therefore the webserver will be
    # rebuilt every time we reconfig. This is because WebStatus.putChild()
    # makes it too difficult to tell whether two instances are the same or
    # not (we'd have to do a recursive traversal of all children to discover
    # all the changes).

    def __init__(self, http_port=None, distrib_port=None, allowForce=None,
                 public_html="public_html", site=None, numbuilds=20,
                 num_events=200, num_events_max=None, auth=None,
                 order_console_by_time=False, changecommentlink=None,
                 revlink=None, projects=None, repositories=None,
                 authz=None, logRotateLength=None, maxRotatedFiles=None,
                 change_hook_dialects = {}, provide_feeds=None):
        """Run a web server that provides Buildbot status.

        @type  http_port: int or L{twisted.application.strports} string
        @param http_port: a strports specification describing which port the
                          buildbot should use for its web server, with the
                          Waterfall display as the root page. For backwards
                          compatibility this can also be an int. Use
                          'tcp:8000' to listen on that port, or
                          'tcp:12345:interface=127.0.0.1' if you only want
                          local processes to connect to it (perhaps because
                          you are using an HTTP reverse proxy to make the
                          buildbot available to the outside world, and do not
                          want to make the raw port visible).

        @type  distrib_port: int or L{twisted.application.strports} string
        @param distrib_port: Use this if you want to publish the Waterfall
                             page using web.distrib instead. The most common
                             case is to provide a string that is an absolute
                             pathname to the unix socket on which the
                             publisher should listen
                             (C{os.path.expanduser(~/.twistd-web-pb)} will
                             match the default settings of a standard
                             twisted.web 'personal web server'). Another
                             possibility is to pass an integer, which means
                             the publisher should listen on a TCP socket,
                             allowing the web server to be on a different
                             machine entirely. Both forms are provided for
                             backwards compatibility; the preferred form is a
                             strports specification like
                             'unix:/home/buildbot/.twistd-web-pb'. Providing
                             a non-absolute pathname will probably confuse
                             the strports parser.

        @param allowForce: deprecated; use authz instead
        @param auth: deprecated; use with authz

        @param authz: a buildbot.status.web.authz.Authz instance giving the authorization
                           parameters for this view

        @param public_html: the path to the public_html directory for this display,
                            either absolute or relative to the basedir.  The default
                            is 'public_html', which selects BASEDIR/public_html.

        @type site: None or L{twisted.web.server.Site}
        @param site: Use this if you want to define your own object instead of
                     using the default.`

        @type numbuilds: int
        @param numbuilds: Default number of entries in lists at the /one_line_per_build
        and /builders/FOO URLs.  This default can be overriden both programatically ---
        by passing the equally named argument to constructors of OneLinePerBuildOneBuilder
        and OneLinePerBuild --- and via the UI, by tacking ?numbuilds=xy onto the URL.

        @type num_events: int
        @param num_events: Default number of events to show in the waterfall.

        @type num_events_max: int
        @param num_events_max: The maximum number of events that are allowed to be
        shown in the waterfall.  The default value of C{None} will disable this
        check

        @type auth: a L{status.web.auth.IAuth} or C{None}
        @param auth: an object that performs authentication to restrict access
                     to the C{allowForce} features. Ignored if C{allowForce}
                     is not C{True}. If C{auth} is C{None}, people can force or
                     stop builds without auth.

        @type order_console_by_time: bool
        @param order_console_by_time: Whether to order changes (commits) in the console
                     view according to the time they were created (for VCS like Git) or
                     according to their integer revision numbers (for VCS like SVN).

        @type changecommentlink: callable, dict, tuple (2 or 3 strings) or C{None}
        @param changecommentlink: adds links to ticket/bug ids in change comments,
            see buildbot.status.web.base.changecommentlink for details

        @type revlink: callable, dict, string or C{None}
        @param revlink: decorations revision ids with links to a web-view,
            see buildbot.status.web.base.revlink for details

        @type projects: callable, dict or c{None}
        @param projects: maps project identifiers to URLs, so that any project listed
            is automatically decorated with a link to it's front page.
            see buildbot.status.web.base.dictlink for details

        @type repositories: callable, dict or c{None}
        @param repositories: maps repository identifiers to URLs, so that any project listed
            is automatically decorated with a link to it's web view.
            see buildbot.status.web.base.dictlink for details

        @type logRotateLength: None or int
        @param logRotateLength: file size at which the http.log is rotated/reset.
            If not set, the value set in the buildbot.tac will be used, 
             falling back to the BuildMaster's default value (1 Mb).
        
        @type maxRotatedFiles: None or int
        @param maxRotatedFiles: number of old http.log files to keep during log rotation.
            If not set, the value set in the buildbot.tac will be used, 
             falling back to the BuildMaster's default value (10 files).       
        
        @type  change_hook_dialects: None or dict
        @param change_hook_dialects: If empty, disables change_hook support, otherwise      
                                     whitelists valid dialects. In the format of
                                     {"dialect1": "Option1", "dialect2", None}
                                     Where the values are options that will be passed
                                     to the dialect
                                     
                                     To enable the DEFAULT handler, use a key of DEFAULT
                                     
                                     
        
    
        @type  provide_feeds: None or list
        @param provide_feeds: If empty, provides atom, json, and rss feeds.
                              Otherwise, a dictionary of strings of
                              the type of feeds provided.  Current
                              possibilities are "atom", "json", and "rss"
        """

        service.MultiService.__init__(self)
        if type(http_port) is int:
            http_port = "tcp:%d" % http_port
        self.http_port = http_port
        if distrib_port is not None:
            if type(distrib_port) is int:
                distrib_port = "tcp:%d" % distrib_port
            if distrib_port[0] in "/~.": # pathnames
                distrib_port = "unix:%s" % distrib_port
        self.distrib_port = distrib_port
        self.num_events = num_events
        if num_events_max:
            assert num_events_max >= num_events
            self.num_events_max = num_events_max
        self.public_html = public_html

        # make up an authz if allowForce was given
        if authz:
            if allowForce is not None:
                raise ValueError("cannot use both allowForce and authz parameters")
            if auth:
                raise ValueError("cannot use both auth and authz parameters (pass "
                                 "auth as an Authz parameter)")
        else:
            # invent an authz
            if allowForce and auth:
                authz = Authz(auth=auth, default_action="auth")
            elif allowForce:
                authz = Authz(default_action=True)
            else:
                if auth:
                    log.msg("Warning: Ignoring authentication. Search for 'authorization'"
                            " in the manual")
                authz = Authz() # no authorization for anything

        self.authz = authz

        self.orderConsoleByTime = order_console_by_time

        # If we were given a site object, go ahead and use it. (if not, we add one later)
        self.site = site

        # store the log settings until we create the site object
        self.logRotateLength = logRotateLength
        self.maxRotatedFiles = maxRotatedFiles        

        # create the web site page structure
        self.childrenToBeAdded = {}
        self.setupUsualPages(numbuilds=numbuilds, num_events=num_events,
                             num_events_max=num_events_max)

        # Set up the jinja templating engine.
        self.templates = createJinjaEnv(revlink, changecommentlink,
                                        repositories, projects)

        # keep track of cached connections so we can break them when we shut
        # down. See ticket #102 for more details.
        self.channels = weakref.WeakKeyDictionary()
        
        # do we want to allow change_hook
        self.change_hook_dialects = {}
        if change_hook_dialects:
            self.change_hook_dialects = change_hook_dialects
            self.putChild("change_hook", ChangeHookResource(dialects = self.change_hook_dialects))

        # Set default feeds
        if provide_feeds is None:
            self.provide_feeds = ["atom", "json", "rss"]
        else:
            self.provide_feeds = provide_feeds

    def setupUsualPages(self, numbuilds, num_events, num_events_max):
        #self.putChild("", IndexOrWaterfallRedirection())
        self.putChild("waterfall", WaterfallStatusResource(num_events=num_events,
                                        num_events_max=num_events_max))
        self.putChild("grid", GridStatusResource())
        self.putChild("console", ConsoleStatusResource(
                orderByTime=self.orderConsoleByTime))
        self.putChild("tgrid", TransposedGridStatusResource())
        self.putChild("builders", BuildersResource()) # has builds/steps/logs
        self.putChild("one_box_per_builder", Redirect("builders"))
        self.putChild("changes", ChangesResource())
        self.putChild("buildslaves", BuildSlavesResource())
        self.putChild("buildstatus", BuildStatusStatusResource())
        self.putChild("one_line_per_build",
                      OneLinePerBuild(numbuilds=numbuilds))
        self.putChild("about", AboutBuildbot())
        self.putChild("authfail", AuthFailResource())


    def __repr__(self):
        if self.http_port is None:
            return "<WebStatus on path %s at %s>" % (self.distrib_port,
                                                     hex(id(self)))
        if self.distrib_port is None:
            return "<WebStatus on port %s at %s>" % (self.http_port,
                                                     hex(id(self)))
        return ("<WebStatus on port %s and path %s at %s>" %
                (self.http_port, self.distrib_port, hex(id(self))))

    def setServiceParent(self, parent):
        service.MultiService.setServiceParent(self, parent)

        # this class keeps a *separate* link to the buildmaster, rather than
        # just using self.parent, so that when we are "disowned" (and thus
        # parent=None), any remaining HTTP clients of this WebStatus will still
        # be able to get reasonable results.
        self.master = parent
        
        def either(a,b): # a if a else b for py2.4
            if a:
                return a
            else:
                return b
        
        rotateLength = either(self.logRotateLength, self.master.log_rotation.rotateLength)
        maxRotatedFiles = either(self.maxRotatedFiles, self.master.log_rotation.maxRotatedFiles)

        if not self.site:
            
            class RotateLogSite(server.Site):
                def _openLogFile(self, path):
                    try:
                        from twisted.python.logfile import LogFile
                        log.msg("Setting up http.log rotating %s files of %s bytes each" %
                                (maxRotatedFiles, rotateLength))            
                        if hasattr(LogFile, "fromFullPath"): # not present in Twisted-2.5.0
                            return LogFile.fromFullPath(path, rotateLength=rotateLength, maxRotatedFiles=maxRotatedFiles)
                        else:
                            log.msg("WebStatus: rotated http logs are not supported on this version of Twisted")
                    except ImportError, e:
                        log.msg("WebStatus: Unable to set up rotating http.log: %s" % e)

                    # if all else fails, just call the parent method
                    return server.Site._openLogFile(self, path)

            # this will be replaced once we've been attached to a parent (and
            # thus have a basedir and can reference BASEDIR)
            root = static.Data("placeholder", "text/plain")
            httplog = os.path.abspath(os.path.join(self.master.basedir, "http.log"))
            self.site = RotateLogSite(root, logPath=httplog)

        # the following items are accessed by HtmlResource when it renders
        # each page.
        self.site.buildbot_service = self

        if self.http_port is not None:
            s = strports.service(self.http_port, self.site)
            s.setServiceParent(self)
        if self.distrib_port is not None:
            f = pb.PBServerFactory(distrib.ResourcePublisher(self.site))
            s = strports.service(self.distrib_port, f)
            s.setServiceParent(self)

        self.setupSite()

    def setupSite(self):
        # this is responsible for creating the root resource. It isn't done
        # at __init__ time because we need to reference the parent's basedir.
        htmldir = os.path.abspath(os.path.join(self.master.basedir, self.public_html))
        if os.path.isdir(htmldir):
            log.msg("WebStatus using (%s)" % htmldir)
        else:
            log.msg("WebStatus: warning: %s is missing. Do you need to run"
                    " 'buildbot upgrade-master' on this buildmaster?" % htmldir)
            # all static pages will get a 404 until upgrade-master is used to
            # populate this directory. Create the directory, though, since
            # otherwise we get internal server errors instead of 404s.
            os.mkdir(htmldir)

        root = StaticFile(htmldir)
        root_page = RootPage()
        root.putChild("", root_page)
        root.putChild("shutdown", root_page)
        root.putChild("cancel_shutdown", root_page)

        for name, child_resource in self.childrenToBeAdded.iteritems():
            root.putChild(name, child_resource)

        status = self.getStatus()
        if "rss" in self.provide_feeds:
            root.putChild("rss", Rss20StatusResource(status))
        if "atom" in self.provide_feeds:
            root.putChild("atom", Atom10StatusResource(status))
        if "json" in self.provide_feeds:
            root.putChild("json", JsonStatusResource(status))

        self.site.resource = root

    def putChild(self, name, child_resource):
        """This behaves a lot like root.putChild() . """
        self.childrenToBeAdded[name] = child_resource

    def registerChannel(self, channel):
        self.channels[channel] = 1 # weakrefs

    def stopService(self):
        for channel in self.channels:
            try:
                channel.transport.loseConnection()
            except:
                log.msg("WebStatus.stopService: error while disconnecting"
                        " leftover clients")
                log.err()
        return service.MultiService.stopService(self)

    def getStatus(self):
        return self.master.getStatus()

    def getChangeSvc(self):
        return self.master.change_svc

    def getPortnum(self):
        # this is for the benefit of unit tests
        s = list(self)[0]
        return s._port.getHost().port

    # What happened to getControl?!
    #
    # instead of passing control objects all over the place in the web
    # code, at the few places where a control instance is required we
    # find the requisite object manually, starting at the buildmaster.
    # This is in preparation for removal of the IControl hierarchy
    # entirely.

# resources can get access to the IStatus by calling
# request.site.buildbot_service.getStatus()
