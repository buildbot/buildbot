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


import urllib
from buildbot.status.web.base import HtmlResource, path_to_builder, \
     path_to_build, css_classes
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

    def content(self, req, cxt):
        s = self.step_status
        b = s.getBuild()

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
                        s = s,
                        result_css = css_classes[b.getResults()]))
        
        template = req.site.buildbot_service.templates.get_template("buildstep.html");        
        return template.render(**cxt)

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

    def content(self, req, ctx):
        return "subpages show data for each step"

    def getChild(self, path, req):
        for s in self.build_status.getSteps():
            if s.getName() == path:
                return StatusResourceBuildStep(self.build_status, s)
        return HtmlResource.getChild(self, path, req)
