
import os, sys, urllib, weakref
from itertools import count

from zope.interface import implements
from twisted.python import log
from twisted.application import strports, service
from twisted.web import server, distrib, static, html
from twisted.spread import pb

from buildbot.interfaces import IControl, IStatusReceiver

from buildbot.status.web.base import HtmlResource, Box, \
     build_get_class, ICurrentBox, OneLineMixin, map_branches, \
     make_stop_form, make_force_build_form
from buildbot.status.web.feeds import Rss20StatusResource, \
     Atom10StatusResource
from buildbot.status.web.waterfall import WaterfallStatusResource
from buildbot.status.web.console import ConsoleStatusResource
from buildbot.status.web.grid import GridStatusResource, TransposedGridStatusResource
from buildbot.status.web.changes import ChangesResource
from buildbot.status.web.builder import BuildersResource
from buildbot.status.web.buildstatus import BuildStatusStatusResource 
from buildbot.status.web.slaves import BuildSlavesResource
from buildbot.status.web.xmlrpc import XMLRPCServer
from buildbot.status.web.about import AboutBuildbot
from buildbot.status.web.auth import IAuth, AuthFailResource

# this class contains the status services (WebStatus and the older Waterfall)
# which can be put in c['status']. It also contains some of the resources
# that are attached to the WebStatus at various well-known URLs, which the
# admin might wish to attach (using WebStatus.putChild) at other URLs.


class LastBuild(HtmlResource):
    def body(self, request):
        return "missing\n"

def getLastNBuilds(status, numbuilds, builders=[], branches=[]):
    """Return a list with the last few Builds, sorted by start time.
    builder_names=None means all builders
    """

    # TODO: this unsorts the list of builder names, ick
    builder_names = set(status.getBuilderNames())
    if builders:
        builder_names = builder_names.intersection(set(builders))

    # to make sure that we get everything, we must get 'numbuilds' builds
    # from *each* source, then sort by ending time, then trim to the last
    # 20. We could be more efficient, but it would require the same
    # gnarly code that the Waterfall uses to generate one event at a
    # time. TODO: factor that code out into some useful class.
    events = []
    for builder_name in builder_names:
        builder = status.getBuilder(builder_name)
        for build_number in count(1):
            if build_number > numbuilds:
                break # enough from this builder, move on to another
            build = builder.getBuild(-build_number)
            if not build:
                break # no more builds here, move on to the next builder
            #if not build.isFinished():
            #    continue
            (build_start, build_end) = build.getTimes()
            event = (build_start, builder_name, build)
            events.append(event)
    def _sorter(a, b):
        return cmp( a[:2], b[:2] )
    events.sort(_sorter)
    # now only return the actual build, and only return some of them
    return [e[2] for e in events[-numbuilds:]]


# /one_line_per_build
#  accepts builder=, branch=, numbuilds=, reload=
class OneLinePerBuild(HtmlResource, OneLineMixin):
    """This shows one line per build, combining all builders together. Useful
    query arguments:

    numbuilds=: how many lines to display
    builder=: show only builds for this builder. Multiple builder= arguments
              can be used to see builds from any builder in the set.
    reload=: reload the page after this many seconds
    """

    title = "Recent Builds"

    def __init__(self, numbuilds=20):
        HtmlResource.__init__(self)
        self.numbuilds = numbuilds

    def getChild(self, path, req):
        status = self.getStatus(req)
        builder = status.getBuilder(path)
        return OneLinePerBuildOneBuilder(builder, numbuilds=self.numbuilds)

    def get_reload_time(self, request):
        if "reload" in request.args:
            try:
                reload_time = int(request.args["reload"][0])
                return max(reload_time, 15)
            except ValueError:
                pass
        return None

    def head(self, request):
        head = ''
        reload_time = self.get_reload_time(request)
        if reload_time is not None:
            head += '<meta http-equiv="refresh" content="%d">\n' % reload_time
        return head

    def body(self, req):
        status = self.getStatus(req)
        control = self.getControl(req)
        numbuilds = int(req.args.get("numbuilds", [self.numbuilds])[0])
        builders = req.args.get("builder", [])
        branches = [b for b in req.args.get("branch", []) if b]

        g = status.generateFinishedBuilds(builders, map_branches(branches),
                                          numbuilds, max_search=numbuilds)

        data = ""

        # really this is "up to %d builds"
        html_branches = map(html.escape, branches)
        data += "<h1>Last %d finished builds: %s</h1>\n" % \
                (numbuilds, ", ".join(html_branches))
        if builders:
            html_builders = map(html.escape, builders)
            data += ("<p>of builders: %s</p>\n" % (", ".join(html_builders)))
        data += "<ul>\n"
        got = 0
        building = False
        online = 0
        for build in g:
            got += 1
            data += " <li>" + self.make_line(req, build) + "</li>\n"
            builder_status = build.getBuilder().getState()[0]
            if builder_status == "building":
                building = True
                online += 1
            elif builder_status != "offline":
                online += 1
        if not got:
            data += " <li>No matching builds found</li>\n"
        data += "</ul>\n"

        if control is not None:
            if building:
                stopURL = "builders/_all/stop"
                data += make_stop_form(stopURL, self.isUsingUserPasswd(req),
                                       True, "Builds")
            if online:
                forceURL = "builders/_all/force"
                data += make_force_build_form(forceURL,
                                              self.isUsingUserPasswd(req), True)

        return data



# /one_line_per_build/$BUILDERNAME
#  accepts branch=, numbuilds=

class OneLinePerBuildOneBuilder(HtmlResource, OneLineMixin):
    def __init__(self, builder, numbuilds=20):
        HtmlResource.__init__(self)
        self.builder = builder
        self.builder_name = builder.getName()
        self.numbuilds = numbuilds
        self.title = "Recent Builds of %s" % self.builder_name

    def body(self, req):
        status = self.getStatus(req)
        numbuilds = int(req.args.get("numbuilds", [self.numbuilds])[0])
        branches = [b for b in req.args.get("branch", []) if b]

        # walk backwards through all builds of a single builder
        g = self.builder.generateFinishedBuilds(map_branches(branches),
                                                numbuilds)

        data = ""
        html_branches = map(html.escape, branches)
        data += ("<h1>Last %d builds of builder %s: %s</h1>\n" %
                 (numbuilds, self.builder_name, ", ".join(html_branches)))
        data += "<ul>\n"
        got = 0
        for build in g:
            got += 1
            data += " <li>" + self.make_line(req, build) + "</li>\n"
        if not got:
            data += " <li>No matching builds found</li>\n"
        data += "</ul>\n"

        return data

# /one_box_per_builder
#  accepts builder=, branch=
class OneBoxPerBuilder(HtmlResource):
    """This shows a narrow table with one row per builder. The leftmost column
    contains the builder name. The next column contains the results of the
    most recent build. The right-hand column shows the builder's current
    activity.

    builder=: show only builds for this builder. Multiple builder= arguments
              can be used to see builds from any builder in the set.
    """

    title = "Latest Build"

    def body(self, req):
        status = self.getStatus(req)
        control = self.getControl(req)

        builders = req.args.get("builder", status.getBuilderNames())
        branches = [b for b in req.args.get("branch", []) if b]

        data = ""

        html_branches = map(html.escape, branches)
        data += "<h2>Latest builds: %s</h2>\n" % ", ".join(html_branches)
        data += "<table>\n"

        building = False
        online = 0
        base_builders_url = self.path_to_root(req) + "builders/"
        for bn in builders:
            base_builder_url = base_builders_url + urllib.quote(bn, safe='')
            builder = status.getBuilder(bn)
            data += "<tr>\n"
            data += '<td class="box"><a href="%s">%s</a></td>\n' \
                  % (base_builder_url, html.escape(bn))
            builds = list(builder.generateFinishedBuilds(map_branches(branches),
                                                         num_builds=1))
            if builds:
                b = builds[0]
                url = (base_builder_url + "/builds/%d" % b.getNumber())
                try:
                    label = b.getProperty("got_revision")
                except KeyError:
                    label = None
                if not label or len(str(label)) > 20:
                    label = "#%d" % b.getNumber()
                text = ['<a href="%s">%s</a>' % (url, label)]
                text.extend(b.getText())
                box = Box(text,
                          class_="LastBuild box %s" % build_get_class(b))
                data += box.td(align="center")
            else:
                data += '<td class="LastBuild box" >no build</td>\n'
            current_box = ICurrentBox(builder).getBox(status)
            data += current_box.td(align="center")

            builder_status = builder.getState()[0]
            if builder_status == "building":
                building = True
                online += 1
            elif builder_status != "offline":
                online += 1

        data += "</table>\n"

        if control is not None:
            if building:
                stopURL = "builders/_all/stop"
                data += make_stop_form(stopURL, self.isUsingUserPasswd(req),
                                       True, "Builds")
            if online:
                forceURL = "builders/_all/force"
                data += make_force_build_form(forceURL,
                                              self.isUsingUserPasswd(req), True)

        return data



HEADER = '''
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN"
 "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">

<html
 xmlns="http://www.w3.org/1999/xhtml"
 lang="en"
 xml:lang="en">
'''

HEAD_ELEMENTS = [
    '<title>%(title)s</title>',
    '<link href="%(root)sbuildbot.css" rel="stylesheet" type="text/css" />',
    ]
BODY_ATTRS = {
    'vlink': "#800080",
    }

FOOTER = '''
</html>
'''


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
     /builders/BUILDERNAME/builds/NUM/tests : summarize test results
     /builders/BUILDERNAME/builds/NUM/tests/TEST.NAME: results of one test
     /builders/_all/{force,stop}: force a build/stop building on all builders.
     /changes : summarize all ChangeSources
     /changes/CHANGENUM: a page describing a single Change
     /schedulers/SCHEDULERNAME: a page describing a Scheduler, including
                                a description of its behavior, a list of the
                                Builders it triggers, and list of the Changes
                                that are queued awaiting the tree-stable
                                timer, and controls to accelerate the timer.
     /buildslaves : list all BuildSlaves
     /buildslaves/SLAVENAME : describe a single BuildSlave
     /one_line_per_build : summarize the last few builds, one line each
     /one_line_per_build/BUILDERNAME : same, but only for a single builder
     /one_box_per_builder : show the latest build and current activity
     /about : describe this buildmaster (Buildbot and support library versions)
     /xmlrpc : (not yet implemented) an XMLRPC server with build status


    All URLs for pages which are not defined here are used to look
    for files in PUBLIC_HTML, which defaults to BASEDIR/public_html.
    This means that /robots.txt or /buildbot.css or /favicon.ico can
    be placed in that directory.

    If an index file (index.html, index.htm, or index, in that order) is
    present in PUBLIC_HTML, it will be used for the root resource. If not,
    the default behavior is to put a redirection to the /waterfall page.

    All of the resources provided by this service use relative URLs to reach
    each other. The only absolute links are the c['projectURL'] links at the
    top and bottom of the page, and the buildbot home-page link at the
    bottom.

    This webserver defines class attributes on elements so they can be styled
    with CSS stylesheets. All pages pull in PUBLIC_HTML/buildbot.css, and you
    can cause additional stylesheets to be loaded by adding a suitable <link>
    to the WebStatus instance's .head_elements attribute.

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

    def __init__(self, http_port=None, distrib_port=None, allowForce=False,
                 public_html="public_html", site=None, numbuilds=20,
                 num_events=200, num_events_max=None, auth=None,
                 order_console_by_time=False):
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

        @param allowForce: boolean, if True then the webserver will allow
                           visitors to trigger and cancel builds

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
        @param num_events: Defaualt number of events to show in the waterfall.

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
        self.allowForce = allowForce
        self.num_events = num_events
        if num_events_max:
            assert num_events_max >= num_events
            self.num_events_max = num_events_max
        self.public_html = public_html

        if self.allowForce and auth:
            assert IAuth.providedBy(auth)
            self.auth = auth
        else:
            if auth:
                log.msg("Warning: Ignoring authentication. allowForce must be"
                        " set to True use this")
            self.auth = None

        self.orderConsoleByTime = order_console_by_time

        # If we were given a site object, go ahead and use it.
        if site:
            self.site = site
        else:
            # this will be replaced once we've been attached to a parent (and
            # thus have a basedir and can reference BASEDIR)
            root = static.Data("placeholder", "text/plain")
            self.site = server.Site(root)
        self.childrenToBeAdded = {}

        self.setupUsualPages(numbuilds=numbuilds, num_events=num_events,
                             num_events_max=num_events_max)

        # the following items are accessed by HtmlResource when it renders
        # each page.
        self.site.buildbot_service = self
        self.header = HEADER
        self.head_elements = HEAD_ELEMENTS[:]
        self.body_attrs = BODY_ATTRS.copy()
        self.footer = FOOTER
        self.template_values = {}

        # keep track of cached connections so we can break them when we shut
        # down. See ticket #102 for more details.
        self.channels = weakref.WeakKeyDictionary()

        if self.http_port is not None:
            s = strports.service(self.http_port, self.site)
            s.setServiceParent(self)
        if self.distrib_port is not None:
            f = pb.PBServerFactory(distrib.ResourcePublisher(self.site))
            s = strports.service(self.distrib_port, f)
            s.setServiceParent(self)

    def setupUsualPages(self, numbuilds, num_events, num_events_max):
        #self.putChild("", IndexOrWaterfallRedirection())
        self.putChild("waterfall", WaterfallStatusResource(num_events=num_events,
                                        num_events_max=num_events_max))
        self.putChild("grid", GridStatusResource())
        self.putChild("console", ConsoleStatusResource(
                orderByTime=self.orderConsoleByTime))
        self.putChild("tgrid", TransposedGridStatusResource())
        self.putChild("builders", BuildersResource()) # has builds/steps/logs
        self.putChild("changes", ChangesResource())
        self.putChild("buildslaves", BuildSlavesResource())
        self.putChild("buildstatus", BuildStatusStatusResource())
        #self.putChild("schedulers", SchedulersResource())
        self.putChild("one_line_per_build",
                      OneLinePerBuild(numbuilds=numbuilds))
        self.putChild("one_box_per_builder", OneBoxPerBuilder())
        self.putChild("xmlrpc", XMLRPCServer())
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
        root = static.File(htmldir)

        for name, child_resource in self.childrenToBeAdded.iteritems():
            root.putChild(name, child_resource)

        status = self.getStatus()
        root.putChild("rss", Rss20StatusResource(status))
        root.putChild("atom", Atom10StatusResource(status))

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

    def getControl(self):
        if self.allowForce:
            return IControl(self.master)
        return None

    def getChangeSvc(self):
        return self.master.change_svc

    def getPortnum(self):
        # this is for the benefit of unit tests
        s = list(self)[0]
        return s._port.getHost().port

    def isUsingUserPasswd(self):
        """Returns boolean to indicate if this WebStatus uses authentication"""
        if self.auth:
            return True
        return False

    def authUser(self, user, passwd):
        """Check that user/passwd is a valid user/pass tuple and can should be
        allowed to perform the action. If this WebStatus is not password
        protected, this function returns False."""
        if not self.isUsingUserPasswd():
            return False
        if self.auth.authenticate(user, passwd):
            return True
        log.msg("Authentication failed for '%s': %s" % (user,
                                                        self.auth.errmsg()))
        return False

# resources can get access to the IStatus by calling
# request.site.buildbot_service.getStatus()

# this is the compatibility class for the old waterfall. It is exactly like a
# regular WebStatus except that the root resource (e.g. http://buildbot.net/)
# always redirects to a WaterfallStatusResource, and the old arguments are
# mapped into the new resource-tree approach. In the normal WebStatus, the
# root resource either redirects the browser to /waterfall or serves
# PUBLIC_HTML/index.html, and favicon/robots.txt are provided by
# having the admin write actual files into PUBLIC_HTML/ .

# note: we don't use a util.Redirect here because HTTP requires that the
# Location: header provide an absolute URI, and it's non-trivial to figure
# out our absolute URI from here.

class Waterfall(WebStatus):

    if hasattr(sys, "frozen"):
        # all 'data' files are in the directory of our executable
        here = os.path.dirname(sys.executable)
        buildbot_icon = os.path.abspath(os.path.join(here, "buildbot.png"))
        buildbot_css = os.path.abspath(os.path.join(here, "classic.css"))
    else:
        # running from source
        # the icon is sibpath(__file__, "../buildbot.png") . This is for
        # portability.
        up = os.path.dirname
        buildbot_icon = os.path.abspath(os.path.join(up(up(up(__file__))),
                                                     "buildbot.png"))
        buildbot_css = os.path.abspath(os.path.join(up(__file__),
                                                    "classic.css"))

    compare_attrs = ["http_port", "distrib_port", "allowForce",
                     "categories", "css", "favicon", "robots_txt"]

    def __init__(self, http_port=None, distrib_port=None, allowForce=True,
                 categories=None, css=buildbot_css, favicon=buildbot_icon,
                 robots_txt=None):
        import warnings
        m = ("buildbot.status.html.Waterfall is deprecated as of 0.7.6 "
             "and will be removed from a future release. "
             "Please use html.WebStatus instead.")
        warnings.warn(m, DeprecationWarning)

        WebStatus.__init__(self, http_port, distrib_port, allowForce)
        self.css = css
        if css:
            if os.path.exists(os.path.join("public_html", "buildbot.css")):
                # they've upgraded, so defer to that copy instead
                pass
            else:
                data = open(css, "rb").read()
                self.putChild("buildbot.css", static.Data(data, "text/css"))
        self.favicon = favicon
        self.robots_txt = robots_txt
        if favicon:
            data = open(favicon, "rb").read()
            self.putChild("favicon.ico", static.Data(data, "image/x-icon"))
        if robots_txt:
            data = open(robots_txt, "rb").read()
            self.putChild("robots.txt", static.Data(data, "text/plain"))
        self.putChild("", WaterfallStatusResource(categories))
