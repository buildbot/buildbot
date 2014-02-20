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
import json

import time, urllib
from twisted.web import html
from twisted.web.util import Redirect
from twisted.web.resource import NoResource
from twisted.internet import defer

from buildbot.status.web.base import HtmlResource, abbreviate_age, \
    BuildLineMixin, ActionResource, path_to_slave, path_to_authzfail, path_to_builder
from buildbot import util
from buildbot.status.web.status_json import SlavesJsonResource, FilterOut


class ShutdownActionResource(ActionResource):

    def __init__(self, slave):
        self.slave = slave
        self.action = "gracefulShutdown"

    @defer.inlineCallbacks
    def performAction(self, request):
        res = yield self.getAuthz(request).actionAllowed(self.action,
                                                        request,
                                                        self.slave)

        url = None
        if res:
            self.slave.setGraceful(True)
            url = path_to_slave(request, self.slave)
        else:
            url = path_to_authzfail(request)
        defer.returnValue(url)

# /buildslaves/$slavename
class OneBuildSlaveResource(HtmlResource, BuildLineMixin):
    addSlash = False
    def __init__(self, slavename):
        HtmlResource.__init__(self)
        self.slavename = slavename

    def getPageTitle(self, req):
        return "Katana - %s" % self.slavename

    def getChild(self, path, req):
        s = self.getStatus(req)
        slave = s.getSlave(self.slavename)
        if path == "shutdown":
            return ShutdownActionResource(slave)
        return Redirect(path_to_slave(req, slave))

    def content(self, request, ctx):        
        s = self.getStatus(request)
        slave = s.getSlave(self.slavename)
        
        my_builders = []
        for bname in s.getBuilderNames():
            b = s.getBuilder(bname)
            for bs in b.getSlaves():
                if bs.getName() == self.slavename:
                    my_builders.append(b)

        # Current builds
        current_builds = []
        for b in my_builders:
            for cb in b.getCurrentBuilds():
                if cb.getSlavename() == self.slavename:                    
                    current_builds.append(self.get_line_values(request, cb))

        try:
            max_builds = int(request.args.get('numbuilds')[0])
        except:
            max_builds = 15
           
        recent_builds = []    
        n = 0
        for rb in s.generateFinishedBuilds(builders=[b.getName() for b in my_builders]):
            if rb.getSlavename() == self.slavename:
                n += 1
                recent_builds.append(self.get_line_values(request, rb))
                if n > max_builds:
                    break

        # connects over the last hour
        slave = s.getSlave(self.slavename)
        connect_count = slave.getConnectCount()

        ctx.update(dict(slave=slave,
                        slavename = self.slavename,  
                        current = current_builds, 
                        recent = recent_builds, 
                        shutdown_url = request.childLink("shutdown"),
                        authz = self.getAuthz(request),
                        this_url = "../../../" + path_to_slave(request, slave),
                        access_uri = slave.getAccessURI()),
                        admin = unicode(slave.getAdmin() or '', 'utf-8'),
                        host = unicode(slave.getHost() or '', 'utf-8'),
                        slave_version = slave.getVersion(),
                        show_builder_column = True,
                        connect_count = connect_count)
        template = request.site.buildbot_service.templates.get_template("buildslave.html")
        data = template.render(**ctx)
        return data

# /buildslaves
class BuildSlavesResource(HtmlResource):
    pageTitle = "Katana Build slaves"
    addSlash = True

    @defer.inlineCallbacks
    def content(self, request, cxt):
        s = self.getStatus(request)

        slaves = SlavesJsonResource(s)
        slaves_dict = yield slaves.asDict(request)
        slaves_dict = FilterOut(slaves_dict)
        cxt['instant_json'] = json.dumps(slaves_dict)

        template = request.site.buildbot_service.templates.get_template("buildslaves.html")
        defer.returnValue(template.render(**cxt))

    def getChild(self, path, req):
        try:
            self.getStatus(req).getSlave(path)
            return OneBuildSlaveResource(path)
        except KeyError:
            return NoResource("No such slave '%s'" % html.escape(path))
