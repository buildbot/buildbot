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
import json
from twisted.python import log
from buildbot.status.web.base import HtmlResource, path_to_builder, path_to_builders, path_to_codebases, path_to_build


class JSONTestResource(HtmlResource):
    def __init__(self, log, step_status):
        HtmlResource.__init__(self)
        self.log = log
        self.step_status = step_status

    def content(self, req, cxt):
        s = self.step_status
        b = s.getBuild()
        builder_status = b.getBuilder()
        project = builder_status.getProject()

        cxt['builder_name'] = builder_status.getFriendlyName()
        cxt['path_to_builder'] = path_to_builder(req, builder_status)
        cxt['path_to_builders'] = path_to_builders(req, project)
        cxt['path_to_codebases'] = path_to_codebases(req, project)
        cxt['path_to_build'] = path_to_build(req, b)
        cxt['build_number'] = b.getNumber()
        cxt['selectedproject'] = project

        try:
            json_data = json.loads(self.log.getText())

            cxt['data'] = json_data

            cxt['results'] = {
                0: 'Inconclusive',
                2: 'Skipped',
                3: 'Ignored',
                4: 'Success',
                5: 'Failure',
                6: 'Error',
                7: 'Cancelled'
            }

        except ValueError as e:
            log.msg("Error with parsing json: {0}".format(e))

        template = req.site.buildbot_service.templates.get_template("jsontestresults.html")
        return template.render(**cxt)
