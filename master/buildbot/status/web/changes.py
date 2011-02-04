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
from twisted.web.error import NoResource

from buildbot.changes.changes import Change
from buildbot.status.web.base import HtmlResource, IBox, Box

class ChangeResource(HtmlResource):
    def __init__(self, change, num):
        self.change = change
        self.title = "Change #%d" % num
        
    def content(self, req, cxt):
        cxt['c'] = self.change.asDict()
        template = req.site.buildbot_service.templates.get_template("change.html")
        data = template.render(cxt)
        return data      

# /changes/NN
class ChangesResource(HtmlResource):

    def content(self, req, cxt):
        cxt['sources'] = self.getStatus(req).getChangeSources()
        template = req.site.buildbot_service.templates.get_template("change_sources.html")
        return template.render(**cxt)
    

    def getChild(self, path, req):
        try:
            num = int(path)
        except ValueError:
            return NoResource("Expected a change number")

        d = self.getStatus(req).getChange(num)
        def cb(change):
            return ChangeResource(change, num)
        def eb(f):
            return NoResource("No change number %d" % num)
        d.addCallbacks(cb, eb)
        return d
    
class ChangeBox(components.Adapter):
    implements(IBox)

    def getBox(self, req):
        url = req.childLink("../changes/%d" % self.original.number)
        template = req.site.buildbot_service.templates.get_template("change_macros.html")
        text = template.module.box_contents(url=url,
                                            who=self.original.getShortAuthor(),
                                            title=self.original.comments)
        return Box([text], class_="Change")
components.registerAdapter(ChangeBox, Change, IBox)

