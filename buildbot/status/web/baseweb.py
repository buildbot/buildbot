
from itertools import count
from zope.interface import implements

from twisted.python import log
from twisted.application import service, strports
from twisted.web import server, distrib, static
from twisted.spread import pb

from buildbot.interfaces import IStatusReceiver, IControl
from buildbot.status.builder import SUCCESS, WARNINGS, FAILURE, EXCEPTION
from buildbot.status.web.waterfall import WaterfallStatusResource
from buildbot.status.web.base import HtmlResource

from buildbot.status.web.changes import StatusResourceChanges
from buildbot.status.web.step import StatusResourceBuildStep
from buildbot.status.web.build import StatusResourceBuild
from buildbot.status.web.builder import StatusResourceBuilder

# this class contains the status services (WebStatus and the older Waterfall)
# which can be put in c['status']. It also contains some of the resources
# that are attached to the WebStatus at various well-known URLs, which the
# admin might wish to attach (using WebStatus.putChild) at other URLs.



class TimelineOfEverything(WaterfallStatusResource):

    def __init__(self):
        HtmlResource.__init__(self)

    def render(self, request):
        webstatus = request.site.webstatus
        self.css = webstatus.css
        self.status = request.site.status
        self.changemaster = webstatus.parent.change_svc
        self.categories = None
        self.title = self.status.getProjectName()
        if self.title is None:
            self.title = "BuildBot"
        return WaterfallStatusResource.render(self, request)


class LastBuild(HtmlResource):
    def body(self, request):
        return "missing\n"

def getLastNBuilds(status, numbuilds, desired_builder_names=None):
    """Return a list with the last few Builds, sorted by start time.
    builder_names=None means all builders
    """

    # TODO: this unsorts the list of builder names, ick
    builder_names = set(status.getBuilderNames())
    if desired_builder_names is not None:
        desired_builder_names = set(desired_builder_names)
        builder_names = builder_names.intersection(desired_builder_names)

    # to make sure that we get everything, we must get 'numbuilds' builds
    # from *each* source, then sort by ending time, then trim to the last
    # 20. We could be more efficient, but it would require the same
    # gnarly code that the Waterfall uses to generate one event at a
    # time.
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


def oneLineForABuild(status, build):
    css_classes = {SUCCESS: "success",
                   WARNINGS: "warnings",
                   FAILURE: "failure",
                   EXCEPTION: "exception",
                   }

    builder_name = build.getBuilder().getName()
    results = build.getResults()
    rev = build.getProperty("got_revision")
    if len(rev) > 20:
        rev = "?"
    values = {'class': css_classes[results],
              'builder_name': builder_name,
              'buildnum': build.getNumber(),
              'results': css_classes[results],
              'buildurl': status.getURLForThing(build),
              'rev': rev,
              }
    fmt = ('<div class="%(class)s">Build '
           '<a href="%(buildurl)s">#%(buildnum)d</a> of '
           '%(builder_name)s [%(rev)s]: '
           '<span class="%(class)s">%(results)s</span></div>\n')
    data = fmt % values
    return data

# /_buildbot/one_line_per_build
class OneLinePerBuild(HtmlResource):
    """This shows one line per build, combining all builders together. Useful
    query arguments:

    numbuilds=: how many lines to display
    builder=: show only builds for this builder. Multiple builder= arguments
              can be used to see builds from any builder in the set.
    """

    def __init__(self, numbuilds=20):
        HtmlResource.__init__(self)
        self.numbuilds = numbuilds

    def getChild(self, path, request):
        status = request.site.status
        builder = status.getBuilder(path)
        return OneLinePerBuildOneBuilder(builder)

    def body(self, request):
        status = request.site.status
        numbuilds = self.numbuilds
        if "numbuilds" in request.args:
            numbuilds = int(request.args["numbuilds"][0])

        desired_builder_names = None
        if "builder" in request.args:
            desired_builder_names = request.args["builder"]
        builds = getLastNBuilds(status, numbuilds, desired_builder_names)
        data = ""
        for build in reversed(builds):
            data += oneLineForABuild(status, build)
        else:
            data += "<div>No matching builds found</div>"
        return data



# /_buildbot/one_line_per_build/$BUILDERNAME
class OneLinePerBuildOneBuilder(HtmlResource):
    def __init__(self, builder, numbuilds=20):
        HtmlResource.__init__(self)
        self.builder = builder
        self.numbuilds = numbuilds

    def body(self, request):
        status = request.site.status
        numbuilds = self.numbuilds
        if "numbuilds" in request.args:
            numbuilds = int(request.args["numbuilds"][0])
        # walk backwards through all builds of a single builder

        # islice is cool but not exactly what we need here
        #events = itertools.islice(b.eventGenerator(), self.numbuilds)

        css_classes = {SUCCESS: "success",
                       WARNINGS: "warnings",
                       FAILURE: "failure",
                       EXCEPTION: "exception",
                       }

        data = ""
        i = 1
        while i < numbuilds:
            build = self.builder.getBuild(-i)
            if not build:
                break
            i += 1

            data += oneLineForABuild(status, build)

        return data



HEADER = '''
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN"
 "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">

<html
 xmlns="http://www.w3.org/1999/xhtml"
 lang="en"
 xml:lang="en">

<head>
  <title>%(title)s</title>
  <link href="%(css_path)s" rel="stylesheet" type="text/css" />
</head>

'''

FOOTER = '''
</html>
'''


class WebStatus(service.MultiService):
    implements(IStatusReceiver)

    """
    The webserver provided by this class has the following resources:

     /waterfall : the big time-oriented 'waterfall' display, with links
                  to individual changes, builders, builds, steps, and logs.
                  A number of query-arguments can be added to influence
                  the display.
     /builders/BUILDERNAME: a page summarizing the builder. This includes
                            references to the Schedulers that feed it,
                            any builds currently in the queue, which
                            buildslaves are designated or attached, and a
                            summary of the build process it uses.
     /builders/BUILDERNAME/builds/NUM: a page describing a single Build
     /builders/BUILDERNAME/builds/NUM/steps/STEPNUM: describes a single step
     /builders/BUILDERNAME/builds/NUM/steps/STEPNUM/logs/LOGNAME: a StatusLog
     /changes/CHANGENUM: a page describing a single Change
     /schedulers/SCHEDULERNAME: a page describing a Scheduler, including
                                a description of its behavior, a list of the
                                Builders it triggers, and list of the Changes
                                that are queued awaiting the tree-stable
                                timer, and controls to accelerate the timer.
     /others...

    All URLs for pages which are not defined here are used to look for files
    in BASEDIR/public_html/ , which means that /robots.txt or /buildbot.css
    can be placed in that directory. If an index file (index.html, index.htm,
    or index, in that order) is present in public_html/, it will be used for
    the root resource. If not, the default behavior is to put a redirection
    to the /waterfall page.

    All of the resources provided by this service use relative URLs to reach
    each other. The only absolute links are the c['projectURL'] links at the
    top and bottom of the page, and the buildbot home-page link at the
    bottom.
    """

    def __init__(self, http_port=None, distrib_port=None,
                 allowForce=False, css="buildbot.css"):
        """Run a web server that provides Buildbot status.

        @param http_port: an int or strports specification that controls where
                          the web server should listen.
        @param distrib_port: an int or strports specification or filename
                             that controls where a twisted.web.distrib socket
                             should listen. If distrib_port is a filename,
                             a unix-domain socket will be used.
        @param allowForce: boolean, if True then the webserver will allow
                           visitors to trigger and cancel builds
        @param css: a URL. If set, the header of each generated page will
                    include a link to add the given URL as a CSS stylesheet
                    for the page.
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
        self.css = css

        self.setupSite()

        if self.http_port is not None:
            s = strports.service(self.http_port, self.site)
            s.setServiceParent(self)
        if self.distrib_port is not None:
            f = pb.PBServerFactory(distrib.ResourcePublisher(self.site))
            s = strports.service(self.distrib_port, f)
            s.setServiceParent(self)

    def setupSite(self):
        # this is responsible for setting self.root and self.site
        self.root = static.File("public_html")
        log.msg("WebStatus using (%s)" % self.root.path)
        self.setupUsualPages(self.root)
        # once we get enabled, we'll stash a reference to the main IStatus
        # instance in site.status, so all of our childrens' render() methods
        # can access it as request.site.status
        self.site = server.Site(self.root)
        self.site.buildbot_service = self
        self.header = HEADER
        self.footer = FOOTER
        self.template_values = {}

    def getStatus(self):
        return self.parent.getStatus()
    def getControl(self):
        if self.allowForce:
            return IControl(self.parent)
        return None

    def setupUsualPages(self, root):
        #root.putChild("", IndexOrWaterfallRedirection())
        root.putChild("waterfall", WaterfallStatusResource())
        #root.putChild("builders", BuildersResource())
        #root.putChild("changes", ChangesResource())
        #root.putChild("schedulers", SchedulersResource())

        root.putChild("one_line_per_build", OneLinePerBuild())

    def putChild(self, name, child_resource):
        self.root.putChild(name, child_resource)

# resources can get access to the IStatus by calling
# request.site.buildbot_service.getStatus()

# this is the compatibility class for the old waterfall. It is exactly like a
# regular WebStatus except that the root resource (e.g. http://buildbot.net/)
# is a WaterfallStatusResource. In the normal WebStatus, the waterfall is at
# e.g. http://builbot.net/waterfall, and the root resource either redirects
# the browser to that or serves BASEDIR/public_html/index.html .
class Waterfall(WebStatus):
    def setupSite(self):
        WebStatus.setupSite(self)
        self.root.putChild("", WaterfallStatusResource())

