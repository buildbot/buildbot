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

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.test.fake import httpclientservice as fakehttpclientservice
from buildbot.test.fake import fakemaster
from buildbot.util.eventual import _setReactor
from buildbot.worker import kubernetes


class FakeBuild(object):
    def render(self, r):
        if isinstance(r, str):
            return "rendered:" + r
        else:
            return r


class FakeBot(object):
    info = {}

    def notifyOnDisconnect(self, n):
        self.n = n

    def remoteSetBuilderList(self, builders):
        return defer.succeed(None)

    def loseConnection(self):
        self.n()


class FakeResult(object):
    code = 204


def mock_delete(*args):
    return defer.succeed(FakeResult())


class KubeClientService(fakehttpclientservice.HTTPClientService):

    def __init__(self, kubeconfig=None, *args, **kwargs):
        fakehttpclientservice.HTTPClientService.__init__(
            self, 'tcp://kubernetes.default', *args, **kwargs)
        self.namespace = 'default'

    @classmethod
    def getFakeService(cls, master, case, *args, **kwargs):
        ret = cls.getService(master, *args, **kwargs)

        def assertNotCalled(self, *_args, **_kwargs):
            case.fail(("KubeClientService called with *{!r}, **{!r}"
                       "while should be called *{!r} **{!r}").format(
                _args, _kwargs, args, kwargs))
        case.patch(kubernetes.KubeClientService, "__init__", assertNotCalled)

        @ret.addCallback
        def assertNoOutstanding(fake):
            fake.case = case
            case.addCleanup(fake.assertNoOutstanding)
            return fake
        return ret


class TestKubernetesWorker(unittest.TestCase):
    worker = None

    def setupWorker(self, *args, **kwargs):
        self.worker = worker = kubernetes.KubeLatentWorker(*args, **kwargs)
        master = fakemaster.make_master(testcase=self, wantData=True)
        self._kube = self.successResultOf(
            KubeClientService.getFakeService(
                master, self))
        worker.setServiceParent(master)
        self.successResultOf(master.startService())

        def cleanup():
            self._kube.delete = mock_delete

        self.addCleanup(master.stopService)
        self.addCleanup(cleanup)
        return worker

    def kube_job_post(self):
        return {
            'apiVersion': 'batch/v1',
            'kind': 'Job',
            'metadata': {
                'name': self.worker.getContainerName()
            },
            'spec': {
                'template': {
                    'metadata': {
                        'name': self.worker.getContainerName()
                    },
                    'spec': {
                        'containers': [{
                            'name': self.worker.getContainerName(),
                            'image': self.worker.image,
                            'env': [
                                {'name': 'BUILDMASTER',
                                 'value': self.worker.masterFQDN},
                                {'name': 'BUILDMASTER_PORT',
                                 'value': '9989'},
                                {'name': 'WORKERNAME',
                                 'value': self.worker.name},
                                {'name': 'WORKERPASS',
                                 'value': self.worker.password}
                            ]
                        }],
                        'restartPolicy': 'Never'
                    }
                }
            }
        }

    def tearDown(self):
        if self.worker is not None:
            class FakeResult(object):
                code = 204

            def delete():
                return defer.succeed(FakeResult())

            self._kube.delete = delete
        _setReactor(None)

    def test_instantiate(self):
        worker = kubernetes.KubeLatentWorker('worker', 'pass')
        # class instantiation configures nothing
        self.assertEqual(getattr(worker, '_kube', None), None)

    def test_wrong_arg(self):
        self.assertRaises(TypeError, self.setupWorker,
            'worker', 'pass', wrong_param='wrong_param')

    def test_service_arg(self):
        self.worker = worker = kubernetes.KubeLatentWorker(
            'worker', 'pass', kubeconfig='kubeconfig')
        master = fakemaster.make_master(testcase=self, wantData=True)
        self._kube = self.successResultOf(
            KubeClientService.getFakeService(
                master, self, kubeconfig='kubeconfig'))
        worker.setServiceParent(master)
        self.successResultOf(master.startService())

    def test_start_service(self):
        self.setupWorker('worker', 'pass')
        # http is lazily created on worker substantiation
        self.assertNotEqual(self.worker._kube, None)

    def test_start_worker(self):
        worker = self.setupWorker('worker', 'pass')
        self._kube.expect(
            method='post',
            ep="/apis/batch/v1/namespaces/default/jobs",
            json=self.kube_job_post(),
            code=201,
            content_json={'metadata': {'name': worker.name}}
        )
        d = worker.substantiate(None, FakeBuild())
        worker.attached(FakeBot())
        self.successResultOf(d)

    def test_start_worker_with_instance_set(self):
        worker = self.setupWorker('worker', 'pass')
        worker.instance = {'metadata': {'name': 'oldname'}}
        self._kube.expect(
            method='delete',
            ep="/apis/batch/v1/namespaces/default/jobs/oldname",
            code=204,
        )
        self._kube.expect(
            method='post',
            ep="/apis/batch/v1/namespaces/default/jobs",
            json=self.kube_job_post(),
            code=201,
            content_json={'metadata': {'name': worker.name}}
        )
        d = worker.substantiate(None, FakeBuild())
        worker.attached(FakeBot())
        self.successResultOf(d)

    def test_start_worker_but_no_connection(self):
        worker = self.setupWorker('worker', 'pass')
        self._kube.expect(
            method='post',
            ep="/apis/batch/v1/namespaces/default/jobs",
            json=self.kube_job_post(),
            code=201,
            content_json={'metadata': {'name': worker.name}}
        )
        worker.substantiate(None, FakeBuild())
        self.assertEqual(worker.instance, {'metadata': {'name': worker.name}})

    def test_start_worker_but_error(self):
        worker = self.setupWorker('worker', 'pass')
        self._kube.expect(
            method='post',
            ep="/apis/batch/v1/namespaces/default/jobs",
            json=self.kube_job_post(),
            code=500,
            content_json={'metadata': {'name': worker.name}}
        )
        d = worker.substantiate(None, FakeBuild())
        self.failureResultOf(d)
        self.assertEqual(worker.instance, None)
        self.successResultOf(d)

    def test_start_worker_with_params(self):
        worker = self.setupWorker('worker', 'pass', kube_extra_spec={
            'spec': {
                'template': {
                    'spec': {
                        'restartPolicy': 'Always'
                    }
                }
            }
        })
        self._kube.expect(
            method='post',
            ep="/apis/batch/v1/namespaces/default/jobs",
            json={
                'apiVersion': 'batch/v1',
                'kind': 'Job',
                'metadata': {
                    'name': self.worker.getContainerName()
                },
                'spec': {
                    'template': {
                        'metadata': {
                            'name': self.worker.getContainerName()
                        },
                        'spec': {
                            'containers': [{
                                'name': self.worker.getContainerName(),
                                'image': self.worker.image,
                                'env': [
                                    {'name': 'BUILDMASTER',
                                     'value': self.worker.masterFQDN},
                                    {'name': 'BUILDMASTER_PORT',
                                     'value': '9989'},
                                    {'name': 'WORKERNAME',
                                     'value': self.worker.name},
                                    {'name': 'WORKERPASS',
                                     'value': self.worker.password},
                                ]
                            }],
                            'restartPolicy': 'Always'
                        }
                    }
                }
            },
            code=201,
            content_json={'metadata': {'name': worker.name}}
        )
        d = worker.substantiate(None, FakeBuild())
        worker.attached(FakeBot())
        self.successResultOf(d)
