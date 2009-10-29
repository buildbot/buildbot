
from zope.interface import implements
from twisted.python import components
from twisted.web.error import NoResource

from buildbot.changes.changes import Change
from buildbot.status.web.base import HtmlResource, StaticHTML, IBox, Box

# /changes/NN
class ChangesResource(HtmlResource):

    def body(self, req):
        template = self.templates.get_template("change_sources.html")
        return template.render(sources = self.getStatus(req).getChangeSources()) + self.footer(req)

    def getChild(self, path, req):
        num = int(path)
        c = self.getStatus(req).getChange(num)
        if not c:
            return NoResource("No change number '%d'" % num)
        return StaticHTML(c.asHTML(), "Change #%d" % num)


class ChangeBox(components.Adapter):
    implements(IBox)

    def getBox(self, req):
        url = req.childLink("../changes/%d" % self.original.number)
        text = self.original.get_HTML_box(url)
        return Box([text], class_="Change")
components.registerAdapter(ChangeBox, Change, IBox)

