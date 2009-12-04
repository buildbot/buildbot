
from twisted.web import html

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
        builder_name = b.getBuilder().getName()
        build_num = b.getNumber()
        data = ""
        data += ('<h1>BuildStep <a href="%s">%s</a>:' %
                 (path_to_builder(req, b.getBuilder()), builder_name))
        data += '<a href="%s">#%d</a>' % (path_to_build(req, b), build_num)
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

        (start, end) = s.getTimes()
        if not start:
            start_text = end_text = elapsed = "Not Started"
        else:
            start_text = ctime(start)
            if end:
                end_text = ctime(end)
                elapsed = util.formatInterval(end - start)
            else:
                end_text = "Not Finished"
                elapsed = util.formatInterval(util.now() - start)

        data += "<h2>Timing</h2>\n"
        data += "<table>\n"
        data += "<tr><td>Start</td><td>%s</td></tr>\n" % start_text
        data += "<tr><td>End</td><td>%s</td></tr>\n" % end_text
        data += "<tr><td>Elapsed</td><td>%s</td></tr>\n" % elapsed
        data += "</table>\n"

        logs = s.getLogs()
        if logs:
            data += ("<h2>Logs</h2>\n"
                     "<ul>\n")
            for logfile in logs:
                logname = logfile.getName()
                if logfile.hasContents():
                    # FIXME: If the step name has a / in it, this is broken
                    # either way.  If we quote it but say '/'s are safe,
                    # it chops up the step name.  If we quote it and '/'s
                    # are not safe, it escapes the / that separates the
                    # step name from the log number.
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
