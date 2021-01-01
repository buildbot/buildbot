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

from buildbot import config
from buildbot.reporters.base import ReporterBase
from buildbot.reporters.generators.build import BuildStatusGenerator
from buildbot.reporters.message import DeprecatedMessageFormatterBuildJson
from buildbot.reporters.message import MessageFormatterEmpty
from buildbot.util import httpclientservice
from buildbot.warnings import warn_deprecated


class HttpStatusPushBase(ReporterBase):
    def checkConfig(self, builders=None, debug=None, verify=None,
                    wantProperties=False, wantSteps=False, wantPreviousBuild=False, wantLogs=False,
                    generators=None, _has_old_arg_names=None):

        old_arg_names = {
            'builders': builders is not None,
            'wantProperties': wantProperties is not False,
            'wantSteps': wantSteps is not False,
            'wantPreviousBuild': wantPreviousBuild is not False,
            'wantLogs': wantLogs is not False,
        }
        if _has_old_arg_names is not None:
            old_arg_names.update(_has_old_arg_names)

        passed_old_arg_names = [k for k, v in old_arg_names.items() if v]

        if passed_old_arg_names:

            old_arg_names_msg = ', '.join(passed_old_arg_names)
            if generators is not None:
                config.error(("can't specify generators and deprecated HTTPStatusPushBase "
                              "arguments ({}) at the same time").format(old_arg_names_msg))
            warn_deprecated('2.9.0',
                            ('The arguments {} passed to {} have been deprecated. Use generators '
                             'instead').format(old_arg_names_msg, self.__class__.__name__))

        if generators is None:
            generators = self._create_generators_from_old_args(builders, wantProperties, wantSteps,
                                                               wantPreviousBuild, wantLogs)

        super().checkConfig(generators=generators)
        httpclientservice.HTTPClientService.checkAvailable(self.__class__.__name__)

    @defer.inlineCallbacks
    def reconfigService(self, builders=None, debug=None, verify=None,
                        wantProperties=False, wantSteps=False,
                        wantPreviousBuild=False, wantLogs=False, generators=None, **kwargs):
        yield super().reconfigService()
        self.debug = debug
        self.verify = verify
        self.builders = builders
        self.wantProperties = wantProperties
        self.wantSteps = wantSteps
        self.wantPreviousBuild = wantPreviousBuild
        self.wantLogs = wantLogs

        if generators is None:
            generators = self._create_generators_from_old_args(builders, wantProperties, wantSteps,
                                                               wantPreviousBuild, wantLogs)

        yield super().reconfigService(generators=generators)

    def _create_generators_from_old_args(self, builders, want_properties, want_steps,
                                         want_previous_build, want_logs):
        formatter = MessageFormatterEmpty(wantProperties=want_properties, wantSteps=want_steps,
                                          wantLogs=want_logs)
        return [
            BuildStatusGenerator(builders=builders, message_formatter=formatter, report_new=True,
                                 mode="all", _want_previous_build=want_previous_build)
        ]

    def sendMessage(self, reports):
        # All reporters that subclass HttpStatusPushBase and are provided by Buildbot implement
        # sendMessage. So the only case when this function is called is when we have a custom
        # reporter that inherits from HttpStatusPushBase.
        warn_deprecated('2.9.0', 'send() in reporters has been deprecated. Use sendMessage()')
        return self.send(reports[0]['builds'][0])

    # Deprecated overridden method, will be removed in Buildbot 3.0
    # def send(self, build):
    #    pass

    def isStatus2XX(self, code):
        return code // 100 == 2


class HttpStatusPush(ReporterBase):
    name = "HttpStatusPush"
    secrets = ['user', 'password', "auth"]

    def checkConfig(self, serverUrl, user=None, password=None, auth=None, headers=None,
                    format_fn=None, builders=None, debug=None, verify=None,
                    wantProperties=False, wantSteps=False,
                    wantPreviousBuild=False, wantLogs=False, generators=None, **kwargs):
        if user is not None and auth is not None:
            config.error("Only one of user/password or auth must be given")
        if user is not None:
            warn_deprecated("0.9.1", "user/password is deprecated, use 'auth=(user, password)'")
        if (format_fn is not None) and not callable(format_fn):
            config.error("format_fn must be a function")

        old_arg_names = {
            'format_fn': format_fn is not None,
            'builders': builders is not None,
            'wantProperties': wantProperties is not False,
            'wantSteps': wantSteps is not False,
            'wantPreviousBuild': wantPreviousBuild is not False,
            'wantLogs': wantLogs is not False,
        }

        passed_old_arg_names = [k for k, v in old_arg_names.items() if v]

        if passed_old_arg_names:

            old_arg_names_msg = ', '.join(passed_old_arg_names)
            if generators is not None:
                config.error(("can't specify generators and deprecated HTTPStatusPushBase "
                              "arguments ({}) at the same time").format(old_arg_names_msg))
            warn_deprecated('2.10.0',
                            ('The arguments {} passed to {} have been deprecated. Use generators '
                             'instead').format(old_arg_names_msg, self.__class__.__name__))

        if generators is None:
            generators = self._create_generators_from_old_args(format_fn, builders, wantProperties,
                                                               wantSteps, wantPreviousBuild,
                                                               wantLogs)

        super().checkConfig(generators=generators, **kwargs)
        httpclientservice.HTTPClientService.checkAvailable(self.__class__.__name__)

    @defer.inlineCallbacks
    def reconfigService(self, serverUrl, user=None, password=None, auth=None, headers=None,
                        format_fn=None, builders=None, debug=None, verify=None,
                        wantProperties=False, wantSteps=False,
                        wantPreviousBuild=False, wantLogs=False, generators=None,
                        **kwargs):
        self.debug = debug
        self.verify = verify
        if user is not None:
            auth = (user, password)
        if format_fn is None:
            format_fn = lambda x: x
        self.format_fn = format_fn  # TODO: remove when send() is removed

        if generators is None:
            generators = self._create_generators_from_old_args(format_fn, builders, wantProperties,
                                                               wantSteps, wantPreviousBuild,
                                                               wantLogs)

        yield super().reconfigService(generators=generators, **kwargs)

        self._http = yield httpclientservice.HTTPClientService.getService(
            self.master, serverUrl, auth=auth, headers=headers,
            debug=self.debug, verify=self.verify)

    def _create_generators_from_old_args(self, format_fn, builders, want_properties, want_steps,
                                         want_logs, want_previous_build):
        formatter = DeprecatedMessageFormatterBuildJson(format_fn,
                                                        wantProperties=want_properties,
                                                        wantSteps=want_steps,
                                                        wantLogs=want_logs)
        return [
            BuildStatusGenerator(builders=builders, message_formatter=formatter, report_new=True,
                                 _want_previous_build=want_previous_build)
        ]

    def is_status_2xx(self, code):
        return code // 100 == 2

    @defer.inlineCallbacks
    def send(self, build):
        # the only case when this function is called is when the user derives this class, overrides
        # send() and calls super().send(build) from there. We'll call format_fn twice in that case,
        # once in generators, once here.
        response = yield self._http.post("", json=self.format_fn(build))
        if not self.is_status_2xx(response.code):
            log.msg("{}: unable to upload status: {}".format(response.code, response.content))

    @defer.inlineCallbacks
    def sendMessage(self, reports):
        if self.send.__func__ is not HttpStatusPush.send:
            warn_deprecated('2.9.0', 'send() in reporters has been deprecated. Use sendMessage()')
            yield self.send(reports[0]['builds'][0])
            return

        response = yield self._http.post("", json=reports[0]['body'])
        if not self.is_status_2xx(response.code):
            log.msg("{}: unable to upload status: {}".format(response.code, response.content))
