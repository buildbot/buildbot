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
from buildbot.status.builder import Results

# /builders/$builder/builds/$buildnum/steps/$stepname
class StatusResourceBuildTest(HtmlResource):
    pageTitle = "Test Result"
    addSlash = True

    def __init__(self, build_status, test_result):
        HtmlResource.__init__(self)
        self.status = build_status
        self.test_result = test_result

    def content(self, req, cxt):
        tr = self.test_result
        b = self.status

        cxt['b'] = self.status
        logs = cxt['logs'] = []
        for lname, log in tr.getLogs().items():
            if isinstance(log, str):
                log = log.decode('utf-8')
            logs.append({'name': lname,
                         'log': log,
                         'link': req.childLink("logs/%s" % urllib.quote(lname)) })

        cxt['text'] = tr.text
        cxt['result_word'] = Results[tr.getResults()]
        cxt.update(dict(builder_link = path_to_builder(req, b.getBuilder()),
                        build_link = path_to_build(req, b),
                        result_css = css_classes[tr.getResults()],
                        b = b,
                        tr = tr))
        
        template = req.site.buildbot_service.templates.get_template("testresult.html")
        return template.render(**cxt)

    def getChild(self, path, req):
        # if path == "logs":
        #    return LogsResource(self.step_status) #TODO we need another class
        return HtmlResource.getChild(self, path, req)



# /builders/$builder/builds/$buildnum/steps
class TestsResource(HtmlResource):
    addSlash = True
    nameDelim = '.'  # Test result have names like a.b.c

    def __init__(self, build_status):
        HtmlResource.__init__(self)
        self.build_status = build_status

    def content(self, req, ctx):
        # TODO list the tests
        return "subpages show data for each test"

    def getChild(self, path, req):
        tpath = None
        if path:
            tpath = tuple(path.split(self.nameDelim))
        if tpath:
            tr = self.build_status.getTestResults().get(tpath)
        if tr:
            return StatusResourceBuildTest(self.build_status, tr)
        return HtmlResource.getChild(self, path, req)
