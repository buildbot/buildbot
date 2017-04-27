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

from __future__ import absolute_import
from __future__ import print_function

import mock


class Client(object):

    def __init__(self, configuration):
        self.configuration = configuration

    def _get_class(self, class_name):
        return type(class_name, (_KubeObj,), {})

    @property
    def BatchV1Api(self):
        return BatchV1Api

    @property
    def V1Job(self):
        return self._get_class('V1Job')

    @property
    def V1ObjectMeta(self):
        return self._get_class('V1ObjectMeta')

    @property
    def V1JobSpec(self):
        return self._get_class('V1JobSpec')

    @property
    def V1PodTemplateSpec(self):
        return self._get_class('V1PodTemplateSpec')

    @property
    def V1PodSpec(self):
        return self._get_class('V1PodSpec')

    @property
    def V1Container(self):
        return self._get_class('V1Container')

    @property
    def V1EnvVar(self):
        return self._get_class('V1EnvVar')


class _KubeObj(mock.Mock):

    def __init__(self, **kwargs):
        super(_KubeObj, self).__init__()
        self.kwargs = kwargs

    @property
    def swagger_types(self):
        return self.kwargs

    def __getattr__(self, key):
        try:
            return self.kwargs[key]
        except KeyError:
            raise AttributeError


class BatchV1Api(object):

    def create_namespaced_job(self, namespace, job):
        return job


class ConfigObj(object):

    def __init__(self):
        self.host = None

    def _set_config(self, config):
        for config_key, value in config.items():
            setattr(self, config_key, value)

    def __repr__(self):
        return 'ConfigObj(%s)' % vars(self)


class ConfigException(object):

    class ConfigException(Exception):
        """Mock of config_exception.ConfigException"""


class Config(object):

    def __init__(self,
                 client_class=Client,
                 config_class=ConfigObj,
                 config_exception=ConfigException):
        self._configuration_obj = config_class()
        self._client_obj = client_class(self._configuration_obj)
        self._config_exception = config_exception
        self._kube_config_file = None
        self._envvar_cluster = None

    def _get_fake_client(self):
        return self._client_obj

    def _get_fake_config(self):
        return self._configuration_obj

    @property
    def config_exception(self):
        return self._config_exception

    def load_kube_config(self):
        if not self._kube_config_file:
            raise IOError()
        elif callable(self._kube_config_file):
            raise self._kube_config_file()
        else:
            config = {
                'host': self._kube_config_file.get('host', 'fake_host')
            }
            self._configuration_obj._set_config(config)

    def load_incluster_config(self):
        if not self._envvar_cluster:
            raise self.config_exception.ConfigException
        elif callable(self._envvar_cluster):
            raise self._envvar_cluster()
        else:
            config = {
                'host': self._envvar_cluster.get('host', 'fake_host')
            }
            self._configuration_obj._set_config(config)
