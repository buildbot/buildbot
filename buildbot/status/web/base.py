
import urlparse, urllib, time, re
import os, cgi, sys, locale
import jinja2
from zope.interface import Interface
from twisted.web import resource, static
from twisted.python import log
from buildbot.status import builder
from buildbot.status.builder import SUCCESS, WARNINGS, FAILURE, SKIPPED, EXCEPTION, RETRY
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
               RETRY: "retry",
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
        locale_enc = locale.getdefaultlocale()[1]
        if locale_enc is not None:
            locale_tz = unicode(time.tzname[time.localtime()[-1]], locale_enc)
        else:
            locale_tz = unicode(time.tzname[time.localtime()[-1]])
        return dict(project_url = status.getProjectURL(),
                    project_name = status.getProjectName(),
                    stylesheet = rootpath + 'default.css',
                    path_to_root = rootpath,
                    version = version,
                    time = time.strftime("%a %d %b %Y %H:%M:%S",
                                        time.localtime(util.now())),
                    tz = locale_tz,
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

# DirectoryLister isn't available in Twisted-2.5.0, and isn't compatible with what
# we need until 9.0.0, so we just skip this particular feature.
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
   Directory Listings require Twisted-9.0.0 or later
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

def createJinjaEnv(revlink=None, changecommentlink=None,
                     repositories=None, projects=None):
    ''' Create a jinja environment changecommentlink is used to
        render HTML in the WebStatus and for mail changes
    
        @type changecommentlink: C{None}, tuple (2 or 3 strings), dict (string -> 2- or 3-tuple) or callable
        @param changecommentlink: see changelinkfilter()

        @type revlink: C{None}, format-string, dict (repository -> format string) or callable
        @param revlink: see revlinkfilter()
        
        @type repositories: C{None} or dict (string -> url)
        @param repositories: an (optinal) mapping from repository identifiers
             (as given by Change sources) to URLs. Is used to create a link
             on every place where a repository is listed in the WebStatus.

        @type projects: C{None} or dict (string -> url)
        @param projects: similar to repositories, but for projects.
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
    
    env.install_null_translations() # needed until we have a proper i18n backend
    
    env.filters.update(dict(
        urlencode = urllib.quote,
        email = emailfilter,
        user = userfilter,
        shortrev = shortrevfilter(revlink, env),
        revlink = revlinkfilter(revlink, env),
        changecomment = changelinkfilter(changecommentlink), 
        repolink = dictlinkfilter(repositories),
        projectlink = dictlinkfilter(projects)
        ))
    
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
        return jinja2.Markup('<div class="user">%s<div class="email">%s</div></div>' % (user, email))
    else:
        return emailfilter(value) # filter for emails here for safety
        
def _revlinkcfg(replace, templates):
    '''Helper function that returns suitable macros and functions
       for building revision links depending on replacement mechanism
'''
   
    assert not replace or callable(replace) or isinstance(replace, dict) or \
           isinstance(replace, str) or isinstance(replace, unicode)
    
    if not replace:
        return lambda rev, repo: None
    else:
        if callable(replace):
            return  lambda rev, repo: replace(rev, repo)
        elif isinstance(replace, dict): # TODO: test for [] instead
            def filter(rev, repo):
                url = replace.get(repo)
                if url:
                    return url % urllib.quote(rev)
                else:
                    return None
                
            return filter
        else:
            return lambda rev, repo: replace % urllib.quote(rev)            
    
    assert False, '_replace has a bad type, but we should never get here'


def _revlinkmacros(replace, templates): 
    '''return macros for use with revision links, depending 
        on whether revlinks are configured or not'''

    macros = templates.get_template("revmacros.html").module

    if not replace:
        id = macros.id
        short = macros.shorten        
    else:
        id = macros.id_replace
        short = macros.shorten_replace            

    return (id, short)
        

def shortrevfilter(replace, templates):
    ''' Returns a function which shortens the revisison string 
        to 12-chars (chosen as this is the Mercurial short-id length) 
        and add link if replacement string is set. 
        
        (The full id is still visible in HTML, for mouse-over events etc.)

        @param replace: see revlinkfilter()
        @param templates: a jinja2 environment
    ''' 
    
    url_f = _revlinkcfg(replace, templates)  
        
    def filter(rev, repo):
        if not rev:
            return u''
            
        id_html, short_html = _revlinkmacros(replace, templates)
        rev = unicode(rev)
        url = url_f(rev, repo)
        rev = jinja2.escape(rev)
        shortrev = rev[:12] # TODO: customize this depending on vc type
        
        if shortrev == rev:
            if url:
                return id_html(rev=rev, url=url) 
            else:
                return rev
        else:
            if url:
                return short_html(short=shortrev, rev=rev, url=url)
            else:
                return shortrev + '...'
        
    return filter


def revlinkfilter(replace, templates):
    ''' Returns a function which adds an url link to a 
        revision identifiers.
   
        Takes same params as shortrevfilter()
        
        @param replace: either a python format string with an %s,
                        or a dict mapping repositories to format strings,
                        or a callable taking (revision, repository) arguments
                          and return an URL (or None, if no URL is available),
                        or None, in which case revisions do not get decorated 
                          with links
   
        @param templates: a jinja2 environment
    ''' 

    url_f = _revlinkcfg(replace, templates)
  
    def filter(rev, repo):
        if not rev:
            return u''
        
        rev = unicode(rev)
        url = url_f(rev, repo)
        if url:
            id_html, _ = _revlinkmacros(replace, templates)
            return id_html(rev=rev, url=url)
        else:
            return jinja2.escape(rev)
    
    return filter
     

def changelinkfilter(changelink):
    ''' Returns function that does regex search/replace in 
        comments to add links to bug ids and similar.
        
        @param changelink: 
            Either C{None}
            or: a tuple (2 or 3 elements) 
                1. a regex to match what we look for 
                2. an url with regex refs (\g<0>, \1, \2, etc) that becomes the 'href' attribute
                3. (optional) an title string with regex ref regex 
            or: a dict mapping projects to above tuples
                (no links will be added if the project isn't found)
            or: a callable taking (changehtml, project) args 
                (where the changetext is HTML escaped in the 
                form of a jinja2.Markup instance) and
                returning another jinja2.Markup instance with 
                the same change text plus any HTML tags added to it.            
    '''

    assert not changelink or isinstance(changelink, dict) or \
        isinstance(changelink, tuple) or callable(changelink)
    
    def replace_from_tuple(t):
        search, url_replace = t[:2]
        if len(t) == 3:
            title_replace = ' title="%s"' % t[2]
        else:
            title_replace = ''
        
        search_re = re.compile(search)
        link_replace_re = jinja2.Markup(r'<a href="%s"%s>\g<0></a>' % (url_replace, title_replace))        

        def filter(text, project):
            text = jinja2.escape(text)
            html = search_re.sub(link_replace_re, text)
            return html

        return filter
    
    if not changelink:
        return lambda text, project: jinja2.escape(text)

    elif isinstance(changelink, dict):
        def dict_filter(text, project):
            # TODO: Optimize and cache return value from replace_from_tuple so
            #       we only compile regex once per project, not per view
            
            t = changelink.get(project)
            if t:
                return replace_from_tuple(t)(text, project)
            else:
                return jinja2.escape(text)
            
        return dict_filter
        
    elif isinstance(changelink, tuple):
        return replace_from_tuple(changelink)
            
    elif callable(changelink):
        def callable_filter(text, project):
            text = jinja2.escape(text)
            return changelink(text, project)
        
        return callable_filter
        
    assert False, 'changelink has unsupported type, but that is checked before'


def dictlinkfilter(links):
    '''A filter that encloses the given value in a link tag
       given that the value exists in the dictionary'''

    assert not links or callable(links) or isinstance(links, dict)
       
    if not links:
        return jinja2.escape

    def filter(key):
        if callable(links):
            url = links(key)            
        else:
            url = links.get(key)

        safe_key = jinja2.escape(key)
            
        if url:
            return jinja2.Markup(r'<a href="%s">%s</a>' % (url, safe_key)) 
        else:
            return safe_key
        
    return filter

class AlmostStrictUndefined(jinja2.StrictUndefined):
    ''' An undefined that allows boolean testing but 
        fails properly on every other use.
        
        Much better than the default Undefined, but not
        fully as strict as StrictUndefined '''
    def __nonzero__(self):
        return False
