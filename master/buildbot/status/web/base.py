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


import cgi
import jinja2
import locale
import os
import re
import sys
import time
import urllib
import urlparse

from buildbot import util
from buildbot import version
from buildbot.process.properties import Properties
from buildbot.status import build
from buildbot.status import builder
from buildbot.status import buildstep
from buildbot.status.results import EXCEPTION
from buildbot.status.results import FAILURE
from buildbot.status.results import RETRY
from buildbot.status.results import SKIPPED
from buildbot.status.results import SUCCESS
from buildbot.status.results import WARNINGS
from twisted.internet import defer
from twisted.python import log
from twisted.web import resource
from twisted.web import server
from twisted.web import static
from twisted.web.util import redirectTo
from zope.interface import Interface


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
    master = req.site.buildbot_service.master
    pname_validate = master.config.validation['property_name']
    pval_validate = master.config.validation['property_value']
    properties = Properties()
    i = 1
    while True:
        pname = req.args.get("property%dname" % i, [""])[0]
        pvalue = req.args.get("property%dvalue" % i, [""])[0]
        if not pname:
            break
        if not pname_validate.match(pname) \
                or not pval_validate.match(pvalue):
            log.msg("bad property name='%s', value='%s'" % (pname, pvalue))
            return None
        properties.setProperty(pname, pvalue, "Force Build Form")
        i = i + 1

    return properties


def build_get_class(b):
    """
    Return the class to use for a finished build or buildstep,
    based on the result.
    """
    # FIXME: this getResults duplicity might need to be fixed
    result = b.getResults()
    if isinstance(b, build.BuildStatus):
        result = b.getResults()
    elif isinstance(b, buildstep.BuildStepStatus):
        result = b.getResults()[0]
        # after forcing a build, b.getResults() returns ((None, []), []), ugh
        if isinstance(result, tuple):
            result = result[0]
    else:
        raise TypeError("%r is not a BuildStatus or BuildStepStatus" % b)

    if result is None:
        # FIXME: this happens when a buildstep is running ?
        return "running"
    return builder.Results[result]


def path_to_root(request):
    # /waterfall : ['waterfall'] -> './'
    # /somewhere/lower : ['somewhere', 'lower'] -> '../'
    # /somewhere/indexy/ : ['somewhere', 'indexy', ''] -> '../../'
    # / : [] -> './'
    if request.prepath:
        segs = len(request.prepath) - 1
    else:
        segs = 0
    root = "../" * segs if segs else './'
    return root


def path_to_authfail(request):
    return path_to_root(request) + "authfail"


def path_to_authzfail(request):
    return path_to_root(request) + "authzfail"


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


def path_always_viewable(request):
    """
    Tests whether an endpoint is viewable irrespective of authz settings.
    If these paths were not accessible by all then the site would fail to
    function, so authz should be ignored.
    """
    return request.path == "/" or request.path == "/login"


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
        if "show_idle" in parms:
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
        props['text'] = text
        return props


class AccessorMixin(object):

    def getStatus(self, request):
        return request.site.buildbot_service.getStatus()

    def getPageTitle(self, request):
        return self.pageTitle

    def getAuthz(self, request):
        return request.site.buildbot_service.authz

    def getBuildmaster(self, request):
        return request.site.buildbot_service.master


class ContextMixin(AccessorMixin):

    def getContext(self, request):
        status = self.getStatus(request)
        rootpath = path_to_root(request)
        locale_enc = locale.getdefaultlocale()[1]
        if locale_enc is not None:
            locale_tz = unicode(time.tzname[time.localtime()[-1]], locale_enc)
        else:
            locale_tz = unicode(time.tzname[time.localtime()[-1]])
        return dict(title_url=status.getTitleURL(),
                    title=status.getTitle(),
                    stylesheet=rootpath + 'default.css',
                    path_to_root=rootpath,
                    version=version,
                    time=time.strftime("%a %d %b %Y %H:%M:%S",
                                       time.localtime(util.now())),
                    tz=locale_tz,
                    metatags=[],
                    pageTitle=self.getPageTitle(request),
                    welcomeurl=rootpath,
                    authz=self.getAuthz(request),
                    request=request,
                    alert_msg=request.args.get("alert_msg", [""])[0],
                    )


class ActionResource(resource.Resource, AccessorMixin):

    """A resource that performs some action, then redirects to a new URL."""

    isLeaf = 1

    def getChild(self, name, request):
        return self

    def performAction(self, request):
        """
        Perform the action, and return the URL to redirect to

        @param request: the web request
        @returns: URL via Deferred
          can also return (URL, alert_msg) to display simple
          feedback to user in case of failure
        """

    def render(self, request):
        d = defer.maybeDeferred(self.getAuthz(request).actionAllowed,
                                'view',
                                request)

        def view(allowed):
            if allowed or path_always_viewable(request):
                return defer.maybeDeferred(lambda: self.performAction(request))
            else:
                return path_to_root(request)
        d.addCallback(view)

        def redirect(url):
            if isinstance(url, tuple):
                url, alert_msg = url
                if alert_msg:
                    url += "?alert_msg=" + urllib.quote(alert_msg, safe='')
            request.redirect(url)
            request.write("see <a href='%s'>%s</a>" % (url, url))
            try:
                request.finish()
            except RuntimeError:
                # this occurs when the client has already disconnected; ignore
                # it (see #2027)
                log.msg("http client disconnected before results were sent")
        d.addCallback(redirect)

        def fail(f):
            request.processingFailed(f)
            return None  # processingFailed will log this for us
        d.addErrback(fail)
        return server.NOT_DONE_YET


class HtmlResource(resource.Resource, ContextMixin):
    # this is a cheap sort of template thingy
    contentType = "text/html; charset=utf-8"
    pageTitle = "Buildbot"
    addSlash = False  # adapted from Nevow

    def getChild(self, path, request):
        if self.addSlash and path == "" and len(request.postpath) == 0:
            return self
        return resource.Resource.getChild(self, path, request)

    def content(self, req, context):
        """
        Generate content using the standard layout and the result of the C{body}
        method.

        This is suitable for the case where a resource just wants to generate
        the body of a page.  It depends on another method, C{body}, being
        defined to accept the request object and return a C{str}.  C{render}
        will call this method and to generate the response body.
        """
        body = self.body(req)
        context['content'] = body
        template = req.site.buildbot_service.templates.get_template(
            "empty.html")
        return template.render(**context)

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

        d = defer.maybeDeferred(self.getAuthz(request).actionAllowed,
                                'view',
                                request)

        def view(allowed):
            if allowed or path_always_viewable(request):
                return defer.maybeDeferred(lambda: self.content(request, ctx))
            else:
                return redirectTo(path_to_root(request), request)
        d.addCallback(view)

        def handle(data):
            if isinstance(data, unicode):
                data = data.encode("utf-8")
            request.setHeader("content-type", self.contentType)
            if request.method == "HEAD":
                request.setHeader("content-length", len(data))
                return ''
            return data
        d.addCallback(handle)

        def ok(data):
            request.write(data)
            try:
                request.finish()
            except RuntimeError:
                # this occurs when the client has already disconnected; ignore
                # it (see #2027)
                log.msg("http client disconnected before results were sent")

        def fail(f):
            request.processingFailed(f)
            return None  # processingFailed will log this for us
        d.addCallbacks(ok, fail)
        return server.NOT_DONE_YET


class StaticHTML(HtmlResource):

    def __init__(self, body, pageTitle):
        HtmlResource.__init__(self)
        self.bodyHTML = body
        self.pageTitle = pageTitle

    def content(self, request, cxt):
        cxt['content'] = self.bodyHTML
        cxt['pageTitle'] = self.pageTitle
        template = request.site.buildbot_service.templates.get_template("empty.html")
        return template.render(**cxt)


class DirectoryLister(static.DirectoryLister, HtmlResource):

    """This variant of the static.DirectoryLister uses a template
    for rendering."""

    def __init__(self, pathname, dirs, contentTypes, contentEncodings, defaultType):
        static.DirectoryLister.__init__(self, pathname, dirs, contentTypes, contentEncodings, defaultType)
        HtmlResource.__init__(self)

    def content(self, request, cxt):
        if self.dirs is None:
            directory = sorted(os.listdir(self.path))
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

    def render(self, request):
        return HtmlResource.render(self, request)


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
HOUR = 60 * MINUTE
DAY = 24 * HOUR
WEEK = 7 * DAY
MONTH = 30 * DAY


def plural(word, words, num):
    if int(num) == 1:
        return "%d %s" % (num, word)
    else:
        return "%d %s" % (num, words)


def abbreviate_age(age):
    if age <= 90:
        return "%s ago" % plural("second", "seconds", age)
    if age < 90 * MINUTE:
        return "about %s ago" % plural("minute", "minutes", age / MINUTE)
    if age < DAY:
        return "about %s ago" % plural("hour", "hours", age / HOUR)
    if age < 2 * WEEK:
        return "about %s ago" % plural("day", "days", age / DAY)
    if age < 2 * MONTH:
        return "about %s ago" % plural("week", "weeks", age / WEEK)
    return "a long time ago"


class BuildLineMixin:
    LINE_TIME_FORMAT = "%b %d %H:%M"

    def get_rev_list(self, build):
        ss_list = build.getSourceStamps()
        all_got_revision = build.getAllGotRevisions() or {}

        if not ss_list:
            return [{
                'repo': 'unknown, no information in build',
                'codebase': '',
                'rev': 'unknown'
            }]

        if len(ss_list) == 1:
            return [{
                'repo': ss_list[0].repository,
                'codebase': ss_list[0].codebase,
                'rev': all_got_revision.get(ss_list[0].codebase, "??")
            }]

        # multiple-codebase configuration
        rev_list = []
        for ss in ss_list:
            # skip codebases with no sourcestamp spec
            if not ss.branch and not ss.revision and not ss.patch and not ss.changes:
                continue

            rev = {
                'repo': ss.repository,
                'codebase': ss.codebase
            }

            # show the most descriptive thing we can
            if ss.branch:
                rev['rev'] = ss.branch
            elif ss.codebase in all_got_revision:
                rev['rev'] = all_got_revision[ss.codebase]
            elif ss.revision:
                rev['rev'] = ss.revision
            else:
                rev['rev'] = '??'

            rev_list.append(rev)

        # if all sourcestamps were empty, then this is a "most recent" kind of build
        if not rev_list:
            rev_list = [{
                'repo': 'unknown, no information in build',
                'codebase': '',
                'rev': 'most recent'
            }]

        return rev_list

    def get_line_values(self, req, build, include_builder=True):
        '''
        Collect the data needed for each line display
        '''
        builder_name = build.getBuilder().getName()
        results = build.getResults()
        css_class = css_classes.get(results, "")

        rev_list = self.get_rev_list(build)

        values = {'class': css_class,
                  'builder_name': builder_name,
                  'buildnum': build.getNumber(),
                  'results': css_class,
                  'text': " ".join(build.getText()),
                  'buildurl': path_to_build(req, build),
                  'builderurl': path_to_builder(req, build.getBuilder()),
                  'rev_list': rev_list,
                  'multiple_revs': (len(rev_list) > 1),
                  'time': time.strftime(self.LINE_TIME_FORMAT,
                                        time.localtime(build.getTimes()[0])),
                  'include_builder': include_builder,
                  'reason': build.getReason(),
                  'interested_users': build.getInterestedUsers(),
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
                   repositories=None, projects=None, jinja_loaders=None,
                   basedir='.'):
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

    all_loaders = [jinja2.FileSystemLoader(os.path.join(basedir, 'templates'))]
    if jinja_loaders:
        all_loaders.extend(jinja_loaders)
    all_loaders.append(jinja2.PackageLoader('buildbot.status.web', 'templates'))
    loader = jinja2.ChoiceLoader(all_loaders)

    env = jinja2.Environment(loader=loader,
                             extensions=['jinja2.ext.i18n'],
                             trim_blocks=True,
                             undefined=AlmostStrictUndefined)

    env.install_null_translations()  # needed until we have a proper i18n backend

    env.tests['mapping'] = lambda obj: isinstance(obj, dict)

    env.filters.update(dict(
        urlencode=urllib.quote,
        email=emailfilter,
        user=userfilter,
        shortrev=shortrevfilter(revlink, env),
        revlink=revlinkfilter(revlink, env),
        changecomment=changelinkfilter(changecommentlink),
        repolink=dictlinkfilter(repositories),
        projectlink=dictlinkfilter(projects)
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
        return emailfilter(value)  # filter for emails here for safety


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
            return lambda rev, repo: replace(rev, repo)
        elif isinstance(replace, dict):  # TODO: test for [] instead
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
        shortrev = rev[:12]  # TODO: customize this depending on vc type

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
    r'''Returns function that does regex search/replace in
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
            title_replace = t[2]
        else:
            title_replace = ''

        search_re = re.compile(search)

        def replacement_unmatched(text):
            return jinja2.escape(text)

        def replacement_matched(mo):
            # expand things *after* application of the regular expressions
            url = jinja2.escape(mo.expand(url_replace))
            title = jinja2.escape(mo.expand(title_replace))
            body = jinja2.escape(mo.group())
            if title:
                return '<a href="%s" title="%s">%s</a>' % (url, title, body)
            else:
                return '<a href="%s">%s</a>' % (url, body)

        def filter(text, project):
            # now, we need to split the string into matched and unmatched portions,
            # quoting the unmatched portions directly and quoting the components of
            # the 'a' element for the matched portions.  We can't use re.split here,
            # because the user-supplied patterns may have multiple groups.
            html = []
            last_idx = 0
            for mo in search_re.finditer(text):
                html.append(replacement_unmatched(text[last_idx:mo.start()]))
                html.append(replacement_matched(mo))
                last_idx = mo.end()
            html.append(replacement_unmatched(text[last_idx:]))
            return jinja2.Markup(''.join(html))

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
                return cgi.escape(text)

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

_charsetRe = re.compile('charset=([^;]*)', re.I)


def getRequestCharset(req):
    """Get the charset for an x-www-form-urlencoded request"""
    # per http://stackoverflow.com/questions/708915/detecting-the-character-encoding-of-an-http-post-request
    hdr = req.getHeader('Content-Type')
    if hdr:
        mo = _charsetRe.search(hdr)
        if mo:
            return mo.group(1).strip()
    return 'utf-8'  # reasonable guess, works for ascii
