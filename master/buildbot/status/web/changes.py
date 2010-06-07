
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
            c = self.getStatus(req).getChange(num)
        except ValueError:
            c = None
            num = path
        if not c:
            return NoResource("No change number '%s'" % path)    
        return ChangeResource(c, num)
    
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

