
from itertools import count
from zope.interface import implements

from twisted.python import log
from twisted.application import service, strports
from twisted.web.resource import Resource
from twisted.web import server, distrib, static
from twisted.spread import pb

from buildbot.interfaces import IStatusReceiver, IControl
from buildbot.status.builder import SUCCESS, WARNINGS, FAILURE, EXCEPTION
from buildbot.status.web.waterfall import WaterfallStatusResource

class ImprovedWaterfall(WaterfallStatusResource):
    def __init__(self):
        WaterfallStatusResource.__init__(self, css="/buildbot.css")

    def getStatus(self, request):
        return request.site.status
    def getControl(self, request):
        return request.site.control
    def getChangemaster(self, request):
        return request.site.changemaster


HEADER = '''
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN"
 "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">

<html
 xmlns="http://www.w3.org/1999/xhtml"
 lang="en"
 xml:lang="en">

'''

FOOTER = '''
</html>
'''

class WebStatus(service.MultiService):
    implements(IStatusReceiver)

    def __init__(self, http_port=None, distrib_port=None, allowForce=False,
                 css=None):
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

        self.root = static.File("public_html")
        log.msg("WebStatus using (%s)" % self.root.path)
        self.setupUsualPages()
        # once we get enabled, we'll stash a reference to the main IStatus
        # instance in site.status, so all of our childrens' render() methods
        # can access it as request.site.status
        self.site = server.Site(self.root)
        self.site.header = HEADER
        self.site.footer = FOOTER
        self.site.css = css

        if self.http_port is not None:
            s = strports.service(self.http_port, self.site)
            s.setServiceParent(self)
        if self.distrib_port is not None:
            f = pb.PBServerFactory(distrib.ResourcePublisher(self.site))
            s = strports.service(self.distrib_port, f)
            s.setServiceParent(self)

    def setupUsualPages(self):
        r = static.Data("This tree contains the built-in status pages\n",
                        "text/plain")
        self.root.putChild("_buildbot", r)
        r.putChild("waterfall", ImprovedWaterfall())
        r.putChild("one_line_per_build", OneLinePerBuild())

    def getStatus(self):
        return self.site.status

    def setServiceParent(self, parent):
        """
        @type  parent: L{buildbot.master.BuildMaster}
        """
        service.MultiService.setServiceParent(self, parent)
        self.setup()

    def setup(self):
        self.site.status = self.parent.getStatus()
        if self.allowForce:
            self.site.control = IControl(self.parent)
        else:
            self.site.control = None
        self.site.changemaster = self.parent.change_svc
        self.site.webstatus = self # TODO: why?
        self.site.basedir = self.parent.basedir # TODO: also why?
        # maybe self.site.head_stuff, to add to <head>

# resources can get access to the site with request.site



class HtmlResource(Resource):
    # this is a cheap sort of template thingy
    css = None
    contentType = "text/html; charset=UTF-8"
    title = "Dummy"
    depth = None # must be specified

    def render(self, request):
        data = self.content(request)
        if isinstance(data, unicode):
            data = data.encode("utf-8")
        request.setHeader("content-type", self.contentType)
        if request.method == "HEAD":
            request.setHeader("content-length", len(data))
            return ''
        return data

    def getCSSlink(self, request):
        css = request.site.css # might be None
        if not css:
            return None
        url = "/".join([".." * self.depth] + [css])
        link = '  <link href="%s" rel="stylesheet" type="text/css"/>\n' % url
        return url
    def make_head(self, request):
        data = ""
        data += '  <title>%s</title>\n' % self.title
        # TODO: use some sort of relative link up to the root page, so
        # this css can be used from child pages too
        csslink = self.getCSSlink(request)
        if csslink:
            data += csslink
        # TODO: favicon
        return data

    def content(self, request):
        data = ""
        data += request.site.header
        data += "<head>\n"
        data += self.make_head(request)
        data += "</head>\n"

        data += '<body vlink="#800080">\n'
        data += self.body(request)
        data += "</body>\n"
        data += request.site.footer
        return data

    def body(self, request):
        return "Dummy\n"

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


