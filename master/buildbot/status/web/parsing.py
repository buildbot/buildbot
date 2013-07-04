from twisted.web import html
import urllib, time
from twisted.python import log
from twisted.internet import defer
from buildbot import interfaces
from buildbot.status.web.base import HtmlResource, BuildLineMixin, \
    path_to_build, path_to_slave, path_to_builder, path_to_builders, path_to_change, \
    path_to_root, ICurrentBox, build_get_class, \
    map_branches, path_to_authzfail, ActionResource, \
    getRequestCharset
from buildbot.schedulers.forcesched import ForceScheduler
from buildbot.schedulers.forcesched import InheritBuildParameter, NestedParameter
from buildbot.schedulers.forcesched import ValidationError
from buildbot.status.web.build import BuildsResource, StatusResourceBuild
from buildbot import util
import collections
import collections
import urllib2
 
    #import easy to use xml parser called minidom:
from xml.dom.minidom import parseString
    #all these imports are standard on most modern python implementations




class XmlResource(HtmlResource):
    pageTitle = "Katana - Codebases"

    def content(self, request, cxt):

        template = request.site.buildbot_service.templates.get_template("log.html")
        template.autoescape = True
        return template.render(**cxt)