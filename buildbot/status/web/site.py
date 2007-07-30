
class StatusResource(Resource):
    status = None
    control = None
    favicon = None
    robots_txt = None

    def __init__(self, status, control, changemaster, categories, css):
        """
        @type  status:       L{buildbot.status.builder.Status}
        @type  control:      L{buildbot.master.Control}
        @type  changemaster: L{buildbot.changes.changes.ChangeMaster}
        """
        Resource.__init__(self)
        self.status = status
        self.control = control
        self.changemaster = changemaster
        self.css = css
        waterfall = WaterfallStatusResource(categories, css)
        waterfall.status = self.status
        waterfall.control = control
        waterfall.changemaster = changemaster
        self.putChild("", waterfall)

    def render(self, request):
        request.redirect(request.prePathURL() + '/')
        request.finish()

    def getChild(self, path, request):
        if path == "robots.txt" and self.robots_txt:
            return static.File(self.robots_txt)
        if path == "buildbot.css" and self.css:
            return static.File(self.css)
        if path == "changes":
            return StatusResourceChanges(self.status, self.changemaster)
        if path == "favicon.ico":
            if self.favicon:
                return static.File(self.favicon)
            return NoResource("No favicon.ico registered")

        if path in self.status.getBuilderNames():
            builder = self.status.getBuilder(path)
            control = None
            if self.control:
                control = self.control.getBuilder(path)
            return StatusResourceBuilder(self.status, builder, control)

        return NoResource("No such Builder '%s'" % path)

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
    buildbot_css = os.path.abspath(os.path.join(up(__file__), "classic.css"))

class Waterfall(base.StatusReceiverMultiService):
    """I implement the primary web-page status interface, called a 'Waterfall
    Display' because builds and steps are presented in a grid of boxes which
    move downwards over time. The top edge is always the present. Each column
    represents a single builder. Each box describes a single Step, which may
    have logfiles or other status information.

    All these pages are served via a web server of some sort. The simplest
    approach is to let the buildmaster run its own webserver, on a given TCP
    port, but it can also publish its pages to a L{twisted.web.distrib}
    distributed web server (which lets the buildbot pages be a subset of some
    other web server).

    Since 0.6.3, BuildBot defines class attributes on elements so they can be
    styled with CSS stylesheets. Buildbot uses some generic classes to
    identify the type of object, and some more specific classes for the
    various kinds of those types. It does this by specifying both in the
    class attributes where applicable, separated by a space. It is important
    that in your CSS you declare the more generic class styles above the more
    specific ones. For example, first define a style for .Event, and below
    that for .SUCCESS

    The following CSS class names are used:
        - Activity, Event, BuildStep, LastBuild: general classes
        - waiting, interlocked, building, offline, idle: Activity states
        - start, running, success, failure, warnings, skipped, exception:
          LastBuild and BuildStep states
        - Change: box with change
        - Builder: box for builder name (at top)
        - Project
        - Time

    @type parent: L{buildbot.master.BuildMaster}
    @ivar parent: like all status plugins, this object is a child of the
                  BuildMaster, so C{.parent} points to a
                  L{buildbot.master.BuildMaster} instance, through which
                  the status-reporting object is acquired.
    """

    compare_attrs = ["http_port", "distrib_port", "allowForce",
                     "categories", "css", "favicon", "robots_txt"]

    def __init__(self, http_port=None, distrib_port=None, allowForce=True,
                 categories=None, css=buildbot_css, favicon=buildbot_icon,
                 robots_txt=None):
        """To have the buildbot run its own web server, pass a port number to
        C{http_port}. To have it run a web.distrib server

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

        @type  allowForce: bool
        @param allowForce: if True, present a 'Force Build' button on the
                           per-Builder page that allows visitors to the web
                           site to initiate a build. If False, don't provide
                           this button.

        @type  favicon: string
        @param favicon: if set, provide the pathname of an image file that
                        will be used for the 'favicon.ico' resource. Many
                        browsers automatically request this file and use it
                        as an icon in any bookmark generated from this site.
                        Defaults to the buildbot/buildbot.png image provided
                        in the distribution. Can be set to None to avoid
                        using a favicon at all.

        @type  robots_txt: string
        @param robots_txt: if set, provide the pathname of a robots.txt file.
                           Many search engines request this file and obey the
                           rules in it. E.g. to disallow them to crawl the
                           status page, put the following two lines in
                           robots.txt::
                              User-agent: *
                              Disallow: /
        """

        base.StatusReceiverMultiService.__init__(self)
        assert allowForce in (True, False) # TODO: implement others
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
        self.categories = categories
        self.css = css
        self.favicon = favicon
        self.robots_txt = robots_txt

    def __repr__(self):
        if self.http_port is None:
            return "<Waterfall on path %s>" % self.distrib_port
        if self.distrib_port is None:
            return "<Waterfall on port %s>" % self.http_port
        return "<Waterfall on port %s and path %s>" % (self.http_port,
                                                       self.distrib_port)

    def setServiceParent(self, parent):
        """
        @type  parent: L{buildbot.master.BuildMaster}
        """
        base.StatusReceiverMultiService.setServiceParent(self, parent)
        self.setup()

    def setup(self):
        status = self.parent.getStatus()
        if self.allowForce:
            control = interfaces.IControl(self.parent)
        else:
            control = None
        change_svc = self.parent.change_svc
        sr = StatusResource(status, control, change_svc, self.categories,
                            self.css)
        sr.favicon = self.favicon
        sr.robots_txt = self.robots_txt
        self.site = server.Site(sr)

        if self.http_port is not None:
            s = strports.service(self.http_port, self.site)
            s.setServiceParent(self)
        if self.distrib_port is not None:
            f = pb.PBServerFactory(distrib.ResourcePublisher(self.site))
            s = strports.service(self.distrib_port, f)
            s.setServiceParent(self)

