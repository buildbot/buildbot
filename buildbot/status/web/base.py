
import urlparse, urllib, time
from zope.interface import Interface
from twisted.web import html, resource, static
from buildbot.status import builder
from buildbot.status.builder import SUCCESS, WARNINGS, FAILURE, SKIPPED, EXCEPTION
from buildbot import version, util
import sys, os, cgi

class ITopBox(Interface):
    """I represent a box in the top row of the waterfall display: the one
    which shows the status of the last build for each builder."""
    def getBox(self, request):
        """Return a Box instance, which can produce a <td> cell.
        """

class ICurrentBox(Interface):
    """I represent the 'current activity' box, just above the builder name."""
    def getBox(self, status):
        """Return a Box instance, which can produce a <td> cell.
        """

class IBox(Interface):
    """I represent a box in the waterfall display."""
    def getBox(self, request):
        """Return a Box instance, which wraps an Event and can produce a <td>
        cell.
        """

class IHTMLLog(Interface):
    pass

css_classes = {SUCCESS: "success",
               WARNINGS: "warnings",
               FAILURE: "failure",
               SKIPPED: "skipped",
               EXCEPTION: "exception",
               }

def td(text="", parms={}, **props):
    data = ""
    data += "  "
    #if not props.has_key("border"):
    #    props["border"] = 1
    props.update(parms)
    comment = props.get("comment", None)
    if comment:
        data += "<!-- %s -->" % comment
    data += "<td"
    class_ = props.get('class_', None)
    if class_:
        props["class"] = class_
    for prop in ("align", "colspan", "rowspan", "border",
                 "valign", "halign", "class"):
        p = props.get(prop, None)
        if p != None:
            data += " %s=\"%s\"" % (prop, p)
    data += ">"
    if not text:
        text = "&nbsp;"
    if isinstance(text, list):
        data += "<br />".join(text)
    else:
        data += text
    data += "</td>\n"
    return data

def build_get_class(b):
    """
    Return the class to use for a finished build or buildstep,
    based on the result.
    """
    # FIXME: this getResults duplicity might need to be fixed
    result = b.getResults()
    #print "THOMAS: result for b %r: %r" % (b, result)
    if isinstance(b, builder.BuildStatus):
        result = b.getResults()
    elif isinstance(b, builder.BuildStepStatus):
        result = b.getResults()[0]
        # after forcing a build, b.getResults() returns ((None, []), []), ugh
        if isinstance(result, tuple):
            result = result[0]
    else:
        raise TypeError, "%r is not a BuildStatus or BuildStepStatus" % b

    if result == None:
        # FIXME: this happens when a buildstep is running ?
        return "running"
    return builder.Results[result]

def path_to_root(request):
    # /waterfall : ['waterfall'] -> ''
    # /somewhere/lower : ['somewhere', 'lower'] -> '../'
    # /somewhere/indexy/ : ['somewhere', 'indexy', ''] -> '../../'
    # / : [] -> ''
    if request.prepath:
        segs = len(request.prepath) - 1
    else:
        segs = 0
    root = "../" * segs
    return root

def path_to_builder(request, builderstatus):
    return (path_to_root(request) +
            "builders/" +
            urllib.quote(builderstatus.getName(), safe=''))

def path_to_build(request, buildstatus):
    return (path_to_builder(request, buildstatus.getBuilder()) +
            "/builds/%d" % buildstatus.getNumber())

def path_to_step(request, stepstatus):
    return (path_to_build(request, stepstatus.getBuild()) +
            "/steps/%s" % urllib.quote(stepstatus.getName(), safe=''))

def path_to_slave(request, slave):
    return (path_to_root(request) +
            "buildslaves/" +
            urllib.quote(slave.getName(), safe=''))

def path_to_change(request, change):
    return (path_to_root(request) +
            "changes/%s" % change.number)

class Box:
    # a Box wraps an Event. The Box has HTML <td> parameters that Events
    # lack, and it has a base URL to which each File's name is relative.
    # Events don't know about HTML.
    spacer = False
    def __init__(self, text=[], class_=None, urlbase=None,
                 **parms):
        self.text = text
        self.class_ = class_
        self.urlbase = urlbase
        self.show_idle = 0
        if parms.has_key('show_idle'):
            del parms['show_idle']
            self.show_idle = 1

        self.parms = parms
        # parms is a dict of HTML parameters for the <td> element that will
        # represent this Event in the waterfall display.

    def td(self, **props):
        props.update(self.parms)
        text = self.text
        if not text and self.show_idle:
            text = ["[idle]"]
        return td(text, props, class_=self.class_)


class HtmlResource(resource.Resource):
    # this is a cheap sort of template thingy
    contentType = "text/html; charset=UTF-8"
    title = "Buildbot"
    addSlash = False # adapted from Nevow

    def getChild(self, path, request):
        if self.addSlash and path == "" and len(request.postpath) == 0:
            return self
        return resource.Resource.getChild(self, path, request)

    def render(self, request):
        # tell the WebStatus about the HTTPChannel that got opened, so they
        # can close it if we get reconfigured and the WebStatus goes away.
        # They keep a weakref to this, since chances are good that it will be
        # closed by the browser or by us before we get reconfigured. See
        # ticket #102 for details.
        if hasattr(request, "channel"):
            # web.distrib.Request has no .channel
            request.site.buildbot_service.registerChannel(request.channel)

        # Our pages no longer require that their URL end in a slash. Instead,
        # they all use request.childLink() or some equivalent which takes the
        # last path component into account. This clause is left here for
        # historical and educational purposes.
        if False and self.addSlash and request.prepath[-1] != '':
            # this is intended to behave like request.URLPath().child('')
            # but we need a relative URL, since we might be living behind a
            # reverse proxy
            #
            # note that the Location: header (as used in redirects) are
            # required to have absolute URIs, and my attempt to handle
            # reverse-proxies gracefully violates rfc2616. This frequently
            # works, but single-component paths sometimes break. The best
            # strategy is to avoid these redirects whenever possible by using
            # HREFs with trailing slashes, and only use the redirects for
            # manually entered URLs.
            url = request.prePathURL()
            scheme, netloc, path, query, fragment = urlparse.urlsplit(url)
            new_url = request.prepath[-1] + "/"
            if query:
                new_url += "?" + query
            request.redirect(new_url)
            return ''

        status = self.getStatus(request)
        ctx = dict(project_url = status.getProjectURL(),
                   project_name = status.getProjectName(),
                   stylesheet = self.path_to_root(request) + 'buildbot.css',
                   version = version,
                   time = time.strftime("%a %d %b %Y %H:%M:%S",
                                        time.localtime(util.now())),
                   tz = time.tzname[time.localtime()[-1]])

        data = self.content(request, ctx)
        if isinstance(data, unicode):
            data = data.encode("utf-8")
        request.setHeader("content-type", self.contentType)
        if request.method == "HEAD":
            request.setHeader("content-length", len(data))
            return ''
        return data

    def getStatus(self, request):
        return request.site.buildbot_service.getStatus()

    def getControl(self, request):
        return request.site.buildbot_service.getControl()

    def isUsingUserPasswd(self, request):
        return request.site.buildbot_service.isUsingUserPasswd()

    def authUser(self, request):
        user = request.args.get("username", ["<unknown>"])[0]
        passwd = request.args.get("passwd", ["<no-password>"])[0]
        if user == "<unknown>" or passwd == "<no-password>":
            return False
        return request.site.buildbot_service.authUser(user, passwd)

    def getChangemaster(self, request):
        return request.site.buildbot_service.getChangeSvc()

    def path_to_root(self, request):
        return path_to_root(request)

    def footer(self, req):
        status = self.getStatus(req)
        template = req.site.buildbot_service.templates.get_template("footer.html")
        return template.render(projectURL = status.getProjectURL(),
                               projectName = status.getProjectName(),
                               welcomeurl = self.path_to_root(req) + "index.html",
                               version = version,
                               time = time.strftime("%a %d %b %Y %H:%M:%S",
                                                    time.localtime(util.now())))

    def getTitle(self, request):
        return self.title

    def fillTemplate(self, template, request):
        s = request.site.buildbot_service
        values = s.template_values.copy()
        values['root'] = self.path_to_root(request)
        # e.g. to reference the top-level 'buildbot.css' page, use
        # "%(root)sbuildbot.css"
        values['title'] = self.getTitle(request)
        return template % values

    def content(self, request, context=None):
        # This method is obsolete.
        # Override in subclasses.

        s = request.site.buildbot_service
        data = ""
        data += self.fillTemplate(s.header, request)
        data += "<head>\n"
        for he in s.head_elements:
            data += " " + self.fillTemplate(he, request) + "\n"        
        data += self.head(request)
        data += "</head>\n\n"

        data += '<body %s>\n' % " ".join(['%s="%s"' % (k,v)
                                          for (k,v) in s.body_attrs.items()])
        data += self.body(request)
        data += "</body>\n"
        data += self.fillTemplate(s.footer, request)
        return data

    def head(self, request):
        return ""

    def body(self, request):
        return "Dummy\n"

class StaticHTML(HtmlResource):
    def __init__(self, body, title):
        HtmlResource.__init__(self)
        self.bodyHTML = body
        self.title = title
    def body(self, request):
        return self.bodyHTML

class DirectoryLister(static.DirectoryLister):
    """This variant of the static.DirectoryLister uses a template
    for rendering."""

    def render(self, request):

        status = request.site.buildbot_service.getStatus()

        cxt = dict(project_url = status.getProjectURL(),
                   project_name = status.getProjectName(),
                   stylesheet = path_to_root(request) + 'buildbot.css',
                   version = version,
                   time = time.strftime("%a %d %b %Y %H:%M:%S",
                                        time.localtime(util.now())))


        if self.dirs is None:
            directory = os.listdir(self.path)
            directory.sort()
        else:
            directory = self.dirs

        dirs, files = self._getFilesAndDirectories(directory)

        cxt['path'] = cgi.escape(urllib.unquote(request.uri))
        cxt['directories'] = dirs
        cxt['files'] = files
        template = request.site.buildbot_service.templates.get_template("directory.html")
        data = template.render(**cxt)
        if isinstance(data, unicode):
            data = data.encode("utf-8")
        return data
        

class StaticFile(static.File):
    """This class adds support for templated directory
    views."""

    def directoryListing(self):
        return DirectoryLister(self.path,
                               self.listNames(),
                               self.contentTypes,
                               self.contentEncodings,
                               self.defaultType)
        

MINUTE = 60
HOUR = 60*MINUTE
DAY = 24*HOUR
WEEK = 7*DAY
MONTH = 30*DAY

def plural(word, words, num):
    if int(num) == 1:
        return "%d %s" % (num, word)
    else:
        return "%d %s" % (num, words)

def abbreviate_age(age):
    if age <= 90:
        return "%s ago" % plural("second", "seconds", age)
    if age < 90*MINUTE:
        return "about %s ago" % plural("minute", "minutes", age / MINUTE)
    if age < DAY:
        return "about %s ago" % plural("hour", "hours", age / HOUR)
    if age < 2*WEEK:
        return "about %s ago" % plural("day", "days", age / DAY)
    if age < 2*MONTH:
        return "about %s ago" % plural("week", "weeks", age / WEEK)
    return "a long time ago"


class BuildLineMixin:
    LINE_TIME_FORMAT = "%b %d %H:%M"

    def get_line_values(self, req, build, include_builder=True):
        '''
        Collect the data needed for each line display
        '''
        builder_name = build.getBuilder().getName()
        results = build.getResults()
        text = build.getText()
        try:
            rev = build.getProperty("got_revision")
            if rev is None:
                rev = "??"
        except KeyError:
            rev = "??"
        rev = str(rev)
        if len(rev) > 40:
            rev = rev[0:40] + "..."
        root = self.path_to_root(req)
        css_class = css_classes.get(results, "")
        values = {'class': css_class,
                  'builder_name': builder_name,
                  'buildnum': build.getNumber(),
                  'results': css_class,
                  'text': " ".join(build.getText()),
                  'buildurl': path_to_build(req, build),
                  'builderurl': path_to_builder(req, build.getBuilder()),
                  'rev': rev,
                  'time': time.strftime(self.LINE_TIME_FORMAT,
                                        time.localtime(build.getTimes()[0])),
                  'text': text if type(text) == str else " ".join(text), 
                  'include_builder': include_builder
                  }
        return values

def map_branches(branches):
    # when the query args say "trunk", present that to things like
    # IBuilderStatus.generateFinishedBuilds as None, since that's the
    # convention in use. But also include 'trunk', because some VC systems
    # refer to it that way. In the long run we should clean this up better,
    # maybe with Branch objects or something.
    if "trunk" in branches:
        return branches + [None]
    return branches
