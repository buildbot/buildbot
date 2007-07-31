
from zope.interface import implements
from twisted.python import components
from twisted.web.error import NoResource
from twisted.web import html

from buildbot.changes.changes import Change
from buildbot.status.web.base import HtmlResource, StaticHTML, IBox, Box

# $changes/NN
class StatusResourceChanges(HtmlResource):
    def __init__(self, status, changemaster):
        HtmlResource.__init__(self)
        self.status = status
        self.changemaster = changemaster
    def body(self, request):
        data = ""
        data += "Change sources:\n"
        sources = list(self.changemaster)
        if sources:
            data += "<ol>\n"
            for s in sources:
                data += "<li>%s</li>\n" % s.describe()
            data += "</ol>\n"
        else:
            data += "none (push only)\n"
        return data
    def getChild(self, path, request):
        num = int(path)
        c = self.changemaster.getChangeNumbered(num)
        if not c:
            return NoResource("No change number '%d'" % num)
        return StaticHTML(c.asHTML(), "Change #%d" % num)


class ChangeBox(components.Adapter):
    implements(IBox)

    def getBox(self):
        url = "changes/%d" % self.original.number
        text = '<a href="%s">%s</a>' % (url, html.escape(self.original.who))
        return Box([text], color="white", class_="Change")
components.registerAdapter(ChangeBox, Change, IBox)
