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


from zope.interface import implements
from twisted.python import components
from twisted.web.resource import NoResource

from buildbot.changes.changes import Change
from buildbot.status.web.base import HtmlResource, IBox, Box

class ChangeResource(HtmlResource):
    def __init__(self, changeid):
        self.changeid = changeid
        self.pageTitle = "Change #%d" % changeid

    def content(self, req, cxt):
        d = self.getStatus(req).getChange(self.changeid)
        def cb(change):
            if not change:
                return "No change number %d" % self.changeid
            templates = req.site.buildbot_service.templates
            cxt['c'] = change.asDict()
            template = templates.get_template("change.html")
            data = template.render(cxt)
            return data
        d.addCallback(cb)
        return d

# /changes/NN
class ChangesResource(HtmlResource):

    def content(self, req, cxt):
        cxt['sources'] = self.getStatus(req).getChangeSources()
        template = req.site.buildbot_service.templates.get_template("change_sources.html")
        return template.render(**cxt)

    def getChild(self, path, req):
        try:
            changeid = int(path)
        except ValueError:
            return NoResource("Expected a change number")

        return ChangeResource(changeid)

class ChangeBox(components.Adapter):
    implements(IBox)

    def getBox(self, req):
        url = req.childLink("../changes/%d" % self.original.number)
        template = req.site.buildbot_service.templates.get_template("change_macros.html")
        text = template.module.box_contents(url=url,
                                            who=self.original.getShortAuthor(),
                                            pageTitle=self.original.comments,
                                            revision=self.original.revision,
                                            project=self.original.project)
        return Box([text], class_="Change")
components.registerAdapter(ChangeBox, Change, IBox)

