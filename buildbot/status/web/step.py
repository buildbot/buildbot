
import urllib
from buildbot.status.web.base import HtmlResource, path_to_builder, \
     path_to_build
from buildbot.status.web.logs import LogsResource
from buildbot import util
from time import ctime

# /builders/$builder/builds/$buildnum/steps/$stepname
class StatusResourceBuildStep(HtmlResource):
    title = "Build Step"
    addSlash = True

    def __init__(self, build_status, step_status):
        HtmlResource.__init__(self)
        self.status = build_status
        self.step_status = step_status

    def body(self, req):
        s = self.step_status
        b = s.getBuild()

        cxt = {}

        logs = cxt['logs'] = []        
        for l in s.getLogs():
            # FIXME: If the step name has a / in it, this is broken
            # either way.  If we quote it but say '/'s are safe,
            # it chops up the step name.  If we quote it and '/'s
            # are not safe, it escapes the / that separates the
            # step name from the log number.
            logs.append({'has_contents': l.hasContents(),
                         'name': l.getName(),
                         'link': req.childLink("logs/%s" % urllib.quote(l.getName())) })

        start, end = s.getTimes()
        
        if start:
            cxt['start'] = ctime(start)
            if end:
                cxt['end'] = ctime(end)
                cxt['elapsed'] = util.formatInterval(end - start)
            else:
                cxt['end'] = "Not Finished"
                cxt['elapsed'] = util.formatInterval(util.now() - start)
        
        cxt.update(dict(builder_link = path_to_builder(req, b.getBuilder()),
                        build_link = path_to_build(req, b),
                        b = b,
                        s = s))
        
        template = req.site.buildbot_service.templates.get_template("buildstep.html");        
        data = template.render(**cxt)


        return data + self.footer(req)

    def getChild(self, path, req):
        if path == "logs":
            return LogsResource(self.step_status)
        return HtmlResource.getChild(self, path, req)



# /builders/$builder/builds/$buildnum/steps
class StepsResource(HtmlResource):
    addSlash = True

    def __init__(self, build_status):
        HtmlResource.__init__(self)
        self.build_status = build_status

    def getChild(self, path, req):
        for s in self.build_status.getSteps():
            if s.getName() == path:
                return StatusResourceBuildStep(self.build_status, s)
        return HtmlResource.getChild(self, path, req)
