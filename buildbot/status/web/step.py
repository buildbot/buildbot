
from twisted.web import html

import urllib
from buildbot.status.web.base import HtmlResource
from buildbot.status.web.logs import LogsResource

# builders/$builder/builds/$buildnum/steps/$stepname
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
        builder_name = b.getBuilder().getName()
        build_num = b.getNumber()
        data = ""
        data += ("<h1>BuildStep <a href=\"../../../../%s\">%s</a>:" %
                 (urllib.quote(builder_name), builder_name))
        data += "<a href=\"../../%d\">#%d</a>" % (build_num, build_num)
        data += ":%s</h1>\n" % s.getName()

        if s.isFinished():
            data += ("<h2>Finished</h2>\n"
                     "<p>%s</p>\n" % html.escape("%s" % s.getText()))
        else:
            data += ("<h2>Not Finished</h2>\n"
                     "<p>ETA %s seconds</p>\n" % s.getETA())

        exp = s.getExpectations()
        if exp:
            data += ("<h2>Expectations</h2>\n"
                     "<ul>\n")
            for e in exp:
                data += "<li>%s: current=%s, target=%s</li>\n" % \
                        (html.escape(e[0]), e[1], e[2])
            data += "</ul>\n"
        logs = s.getLogs()
        if logs:
            data += ("<h2>Logs</h2>\n"
                     "<ul>\n")
            for logfile in logs:
                if logfile.hasContents():
                    # FIXME: If the step name has a / in it, this is broken
                    # either way.  If we quote it but say '/'s are safe,
                    # it chops up the step name.  If we quote it and '/'s
                    # are not safe, it escapes the / that separates the
                    # step name from the log number.
                    logname = logfile.getName()
                    logurl = req.childLink("logs/%s" % urllib.quote(logname))
                    data += ('<li><a href="%s">%s</a></li>\n' % 
                             (logurl, html.escape(logname)))
                else:
                    data += '<li>%s</li>\n' % html.escape(logname)
            data += "</ul>\n"

        return data

    def getChild(self, path, req):
        if path == "logs":
            return LogsResource(self.step_status)
        return HtmlResource.getChild(self, path, req)



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
