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


class Client(object):

    def __init__(self, configuration):
        self.configuration = configuration

    @property
    def BatchV1Api(self):
        return BatchV1Api


class BatchV1Api(object):

    def create_namespaced_job(self, namespace, job):
        return ResponseJob(job)


class _DummyClass(object):
    """Dummy class to set attribute"""


class ResponseJob(object):

    def __init__(self, job_dict):
        self._job_dict = job_dict
        self.metadata = metadata = _DummyClass()
        metadata.name = job_dict['metadata']['name']
        metadata.namespace = job_dict['metadata'].get('namespace', 'default')
        self.spec = spec = _DummyClass()
        spec.template = template = _DummyClass()
        template.spec = container_spec = _DummyClass()
        container_spec.containers = containers_list = list()
        container = _DummyClass()
        containers_list.append(container)
        image = job_dict["spec"]["template"]["spec"]["containers"][0]["image"]
        container.image = image


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
