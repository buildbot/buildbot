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

from twisted.internet import defer
from twisted.python import log

from buildbot.reporters.base import ReporterBase
from buildbot.reporters.generators.build import BuildStatusGenerator
from buildbot.reporters.message import MessageFormatterFunction
from buildbot.util import httpclientservice


class HttpStatusPush(ReporterBase):
    name = "HttpStatusPush"
    secrets = ["auth"]

    def checkConfig(self, serverUrl, auth=None, headers=None,
                    debug=None, verify=None, generators=None, **kwargs):

        if generators is None:
            generators = self._create_default_generators()

        super().checkConfig(generators=generators, **kwargs)
        httpclientservice.HTTPClientService.checkAvailable(self.__class__.__name__)

    @defer.inlineCallbacks
    def reconfigService(self, serverUrl, auth=None, headers=None,
                        debug=None, verify=None, generators=None,
                        **kwargs):
        self.debug = debug
        self.verify = verify

        if generators is None:
            generators = self._create_default_generators()

        yield super().reconfigService(generators=generators, **kwargs)

        self._http = yield httpclientservice.HTTPClientService.getService(
            self.master, serverUrl, auth=auth, headers=headers,
            debug=self.debug, verify=self.verify)

    def _create_default_generators(self):
        formatter = MessageFormatterFunction(lambda context: context['build'], 'json')
        return [
            BuildStatusGenerator(message_formatter=formatter, report_new=True)
        ]

    def is_status_2xx(self, code):
        return code // 100 == 2

    @defer.inlineCallbacks
    def sendMessage(self, reports):
        response = yield self._http.post("", json=reports[0]['body'])
        if not self.is_status_2xx(response.code):
            log.msg("{}: unable to upload status: {}".format(response.code, response.content))
