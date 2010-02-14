
import urlparse, urllib, time, re
import os, cgi, sys
import jinja2
from zope.interface import Interface
from twisted.web import resource, static
from twisted.web.static import redirectTo
from twisted.python import log
from buildbot.status import builder
from buildbot.status.builder import SUCCESS, WARNINGS, FAILURE, SKIPPED, EXCEPTION
from buildbot import version, util
from buildbot.process.properties import Properties

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
               None: "",
               }


def getAndCheckProperties(req):
    """
Fetch custom build properties from the HTTP request of a "Force build" or
"Resubmit build" HTML form.
Check the names for valid strings, and return None if a problem is found.
Return a new Properties object containing each property found in req.
"""
    properties = Properties()
    for i in (1,2,3):
        pname = req.args.get("property%dname" % i, [""])[0]
        pvalue = req.args.get("property%dvalue" % i, [""])[0]
        if pname and pvalue:
            if not re.match(r'^[\w\.\-\/\~:]*$', pname) \
                    or not re.match(r'^[\w\.\-\/\~:]*$', pvalue):
                log.msg("bad property name='%s', value='%s'" % (pname, pvalue))
                return None
            properties.setProperty(pname, pvalue, "Force Build Form")
    return properties

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

def path_to_authfail(request):
    return path_to_root(request) + "/authfail"

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
        props['class'] = self.class_
        props['text'] = text;
        return props    
    
    
class ContextMixin(object):
    def getContext(self, request):
        status = self.getStatus(request)
        rootpath = path_to_root(request)
        return dict(project_url = status.getProjectURL(),
                    project_name = status.getProjectName(),
                    stylesheet = rootpath + 'default.css',
                    path_to_root = rootpath,
                    version = version,
                    time = time.strftime("%a %d %b %Y %H:%M:%S",
                                        time.localtime(util.now())),
                    tz = time.tzname[time.localtime()[-1]],
                    metatags = [],
                    title = self.getTitle(request),
                    welcomeurl = rootpath)

    def getStatus(self, request):
        return request.site.buildbot_service.getStatus()    
        
    def getTitle(self, request):
        return self.title

class HtmlResource(resource.Resource, ContextMixin):
    # this is a cheap sort of template thingy
    contentType = "text/html; charset=utf-8"
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

        ctx = self.getContext(request)

        data = self.content(request, ctx)
        if isinstance(data, unicode):
            data = data.encode("utf-8")
        request.setHeader("content-type", self.contentType)
        if request.method == "HEAD":
            request.setHeader("content-length", len(data))
            return ''
        return data

    def getAuthz(self, request):
        return request.site.buildbot_service.authz

    def getBuildmaster(self, request):
        return request.site.buildbot_service.master

    def getChangemaster(self, request):
        return request.site.buildbot_service.getChangeSvc()


class StaticHTML(HtmlResource):
    def __init__(self, body, title):
        HtmlResource.__init__(self)
        self.bodyHTML = body
        self.title = title
    def content(self, request, cxt):
        cxt['content'] = self.bodyHTML
        cxt['title'] = self.title
        template = request.site.buildbot_service.templates.get_template("empty.html")
        return template.render(**cxt)

# DirectoryLister isn't available in Twisted-2.5.0, so we just skip
# this particular feature.
have_DirectoryLister = False
if hasattr(static, 'DirectoryLister'):
    have_DirectoryLister = True
    class DirectoryLister(static.DirectoryLister, ContextMixin):
        """This variant of the static.DirectoryLister uses a template
        for rendering."""

        title = 'BuildBot'

        def render(self, request):
            cxt = self.getContext(request)

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
        if have_DirectoryLister:
            return DirectoryLister(self.path,
                                   self.listNames(),
                                   self.contentTypes,
                                   self.contentEncodings,
                                   self.defaultType)
        else:
            return static.Data("""
   Directory Listings require Twisted-8.0.0 or later
                """, "text/plain")
        

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
        css_class = css_classes.get(results, "")

        if type(text) == list:
            text = " ".join(text)            

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
                  'text': text,
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


# jinja utilities 

def createJinjaEnv(revlink=None, changecommentlink=None):
    ''' Create a jinja environment changecommentlink is used to
        render HTML in the WebStatus and for mail changes
    
        @type changecommentlink: tuple (2 strings) or C{None}
        @param changecommentlink: a regular expression and replacement string that is applied
                     to all change comments. The first element represents what to search
                     for and the second yields an url (the <a href=""></a> is added outside this)
                     I.e. for Trac: (r'#(\d+)', r'http://buildbot.net/trac/ticket/\1') 

        @type revlink: string or C{None}
        @param revlink: a replacement string that is applied to all revisions and
                        will, if set, create a link to the result of the replacement.
                        Use %s to insert the revision id in the url. 
                        I.e. for Buildbot on github: ('http://github.com/djmitche/buildbot/tree/%s') 
                        (The revision id will be URL encoded before inserted in the replacement string)
    '''
    
    # See http://buildbot.net/trac/ticket/658
    assert not hasattr(sys, "frozen"), 'Frozen config not supported with jinja (yet)'

    default_loader = jinja2.PackageLoader('buildbot.status.web', 'templates')
    root = os.path.join(os.getcwd(), 'templates')
    loader = jinja2.ChoiceLoader([jinja2.FileSystemLoader(root),
                                  default_loader])
    env = jinja2.Environment(loader=loader,
                             extensions=['jinja2.ext.i18n'],
                             trim_blocks=True,
                             undefined=AlmostStrictUndefined)
    
    env.filters['urlencode'] = urllib.quote
    env.filters['email'] = emailfilter
    env.filters['user'] = userfilter
    env.filters['shortrev'] = shortrevfilter(revlink, env)
    env.filters['revlink'] = revlinkfilter(revlink, env)
    
    if changecommentlink:
        env.filters['changecomment'] = addlinkfilter(*changecommentlink) 
    else:
        env.filters['changecomment'] = jinja2.escape
            
    return env    

def emailfilter(value):
    ''' Escape & obfuscate e-mail addresses
    
        replacing @ with <span style="display:none> reportedly works well against web-spiders
        and the next level is to use rot-13 (or something) and decode in javascript '''    
    
    user = jinja2.escape(value)
    obfuscator = jinja2.Markup('<span style="display:none">ohnoyoudont</span>@')
    output = user.replace('@', obfuscator)
    return output
 
 
def userfilter(value):
    ''' Hide e-mail address from user name when viewing changes
    
        We still include the (obfuscated) e-mail so that we can show
        it on mouse-over or similar etc 
    '''
    r = re.compile('(.*) +<(.*)>')
    m = r.search(value)
    if m:
        user = jinja2.escape(m.group(1))
        email = emailfilter(m.group(2))        
        email = jinja2.Markup('<div class="email">%s</div>') % email
        return jinja2.Markup('<div class="user">%s%s</div>' % (user, email))
    else:
        return jinja2.escape(value)
        

def shortrevfilter(replace, templates):
    ''' Returns a function which shortens the revisison string 
        to 12-chars (Mercurial short-id)
        and add link if replacement string is set. 
        
        (The full id is still visible in HTML, for mouse-over events etc.)

        TODO: Add a 'source' argument to SourceStamp and apply it here

        @param replace: a python format string with an %s
        @param templates: a jinja2 environment
    ''' 
    
    def filter(value):
        if not value:
            return u''

        macros = templates.get_template("revmacros.html").module
        value = unicode(value)
        
        if replace:
            id_html = macros.id_replace
            short_html = macros.shorten_replace            
            url = replace % urllib.quote(value)
        else:
            id_html = macros.id
            short_html = macros.shorten
            url = None
 
        value = jinja2.escape(value)
        short = value[:12]
        
        if short == value:
            return id_html(rev=value, url=url) 
        else:
            return short_html(short=short, rev=value, url=url)
        
    return filter


def revlinkfilter(replace, templates):
    ''' Returns a function which adds an url link to a 
        revision identifiers.
        
        @param replace: a python format string with an %s
        @param templates: a jinja2 environment
    ''' 
        
    def filter(value):
        if not value:
            return u''
        
        macros = templates.get_template("revmacros.html").module    
        value = unicode(value)

        if replace:
            html = macros.id_replace
            url = replace % urllib.quote(value)
        else:
            html = macros.id  
            url = None
            
        return html(rev=value, url=url)
    
    return filter
     

def addlinkfilter(search, url_replace, title_replace=''):
    ''' Returns function that does regex search/replace in 
        comments to add links to bug ids and similar.
        
        @param search: a regex to match what we look for 
        @param url_replace: an url with regex refs (\g<0>, \1, \2, etc) that becomes the 'href' attribute
        @param title_replace: similar to url_replace, but for the 'title' attribute
    '''
    
    regex = re.compile(search)
    link_replace = jinja2.Markup(r'<a href="%s" title="%s">\g<0></a>' % 
                                 (url_replace, title_replace))
    
    def filter(value):
        return regex.sub(link_replace, value)
    
    return filter


class AlmostStrictUndefined(jinja2.StrictUndefined):
    ''' An undefined that allows boolean testing but 
        fails properly on every other use.
        
        Much better than the default Undefined, but not
        fully as strict as StrictUndefined '''
    def __nonzero__(self):
        return False
