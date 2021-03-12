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


import importlib
import inspect
import os
import pkg_resources
import warnings

import twisted
from twisted.trial import unittest
from twisted.trial.unittest import SkipTest

from buildbot.interfaces import IBuildStep
from buildbot.interfaces import IChangeSource
from buildbot.interfaces import IScheduler
from buildbot.interfaces import IWorker
from buildbot.plugins.db import get_plugins


def get_python_module_contents(package_name):
    spec = importlib.util.find_spec(package_name)
    if spec is None or spec.origin is None:
        return set()

    pathname = os.path.dirname(spec.origin)
    result = set()

    with os.scandir(pathname) as dir_entries:
        for dir_entry in dir_entries:
            filename = dir_entry.name

            if filename.startswith('__'):
                continue
            next_package_name = '.'.join((package_name, filename.partition('.')[0]))

            if dir_entry.is_file() and filename.endswith('.py'):
                result.add(next_package_name)

            if dir_entry.is_dir():
                result.add(next_package_name)
                result |= get_python_module_contents(next_package_name)

    return result


# NOTE: when running this test locally, make sure to reinstall master after every change to pick up
# new entry points.
class TestSetupPyEntryPoints(unittest.TestCase):
    def test_changes(self):
        self.verify_plugins_registered('changes', 'buildbot.changes', IChangeSource)

    def test_schedulers(self):
        self.verify_plugins_registered('schedulers', 'buildbot.schedulers', IScheduler)

    def test_steps(self):
        self.verify_plugins_registered('steps', 'buildbot.steps', IBuildStep)

    def test_util(self):
        # work around Twisted bug 9384.
        if pkg_resources.parse_version(twisted.__version__) < pkg_resources.parse_version("18.9.0"):
            raise SkipTest('manhole.py can not be imported on old twisted and new python')

        known_not_exported = {
            'buildbot.util._notifier.Notifier',
            'buildbot.util.bbcollections.KeyedSets',
            'buildbot.util.codebase.AbsoluteSourceStampsMixin',
            'buildbot.util.config.ConfiguredMixin',
            'buildbot.util.croniter.croniter',
            'buildbot.util.debounce.Debouncer',
            'buildbot.util.deferwaiter.DeferWaiter',
            'buildbot.util.deferwaiter.RepeatedActionHandler',
            'buildbot.util.git.GitMixin',
            'buildbot.util.git.GitStepMixin',
            'buildbot.util.giturlparse.GitUrl',
            'buildbot.util.httpclientservice.HTTPClientService',
            'buildbot.util.httpclientservice.TxRequestsResponseWrapper',
            'buildbot.util.kubeclientservice.KubeClientService',
            'buildbot.util.kubeclientservice.KubeConfigLoaderBase',
            'buildbot.util.kubeclientservice.KubeError',
            'buildbot.util.latent.CompatibleLatentWorkerMixin',
            'buildbot.util.lineboundaries.LineBoundaryFinder',
            'buildbot.util.lru.AsyncLRUCache',
            'buildbot.util.lru.LRUCache',
            'buildbot.util.maildir.MaildirService',
            'buildbot.util.maildir.NoSuchMaildir',
            'buildbot.util.netstrings.NetstringParser',
            'buildbot.util.netstrings.NullAddress',
            'buildbot.util.netstrings.NullTransport',
            'buildbot.util.pathmatch.Matcher',
            'buildbot.util.poll.Poller',
            'buildbot.util.private_tempdir.PrivateTemporaryDirectory',
            'buildbot.util.protocol.LineBuffer',
            'buildbot.util.protocol.LineProcessProtocol',
            'buildbot.util.pullrequest.PullRequestMixin',
            'buildbot.util.raml.RamlLoader',
            'buildbot.util.raml.RamlSpec',
            'buildbot.util.sautils.InsertFromSelect',
            'buildbot.util.service.AsyncMultiService',
            'buildbot.util.service.AsyncService',
            'buildbot.util.service.BuildbotService',
            'buildbot.util.service.BuildbotServiceManager',
            'buildbot.util.service.ClusteredBuildbotService',
            'buildbot.util.service.MasterService',
            'buildbot.util.service.ReconfigurableServiceMixin',
            'buildbot.util.service.SharedService',
            'buildbot.util.state.StateMixin',
            'buildbot.util.subscription.Subscription',
            'buildbot.util.subscription.SubscriptionPoint',
            'buildbot.util.test_result_submitter.TestResultSubmitter',
        }
        self.verify_plugins_registered('util', 'buildbot.util', None, known_not_exported)

    def test_reporters(self):
        known_not_exported = {
            'buildbot.reporters.base.ReporterBase',
            'buildbot.reporters.generators.utils.BuildStatusGeneratorMixin',
            'buildbot.reporters.gerrit.DEFAULT_REVIEW',
            'buildbot.reporters.gerrit.DEFAULT_SUMMARY',
            'buildbot.reporters.irc.IRCChannel',
            'buildbot.reporters.irc.IRCContact',
            'buildbot.reporters.irc.IrcStatusBot',
            'buildbot.reporters.irc.IrcStatusFactory',
            'buildbot.reporters.irc.UsageError',
            'buildbot.reporters.mail.Domain',
            'buildbot.reporters.message.MessageFormatterBase',
            'buildbot.reporters.message.MessageFormatterBaseJinja',
            'buildbot.reporters.telegram.TelegramChannel',
            'buildbot.reporters.telegram.TelegramContact',
            'buildbot.reporters.telegram.TelegramPollingBot',
            'buildbot.reporters.telegram.TelegramStatusBot',
            'buildbot.reporters.telegram.TelegramWebhookBot',
            'buildbot.reporters.words.Channel',
            'buildbot.reporters.words.Contact',
            'buildbot.reporters.words.ForceOptions',
            'buildbot.reporters.words.StatusBot',
            'buildbot.reporters.words.ThrottledClientFactory',
            'buildbot.reporters.words.UsageError',
            'buildbot.reporters.words.WebhookResource',
        }
        self.verify_plugins_registered('reporters', 'buildbot.reporters', None, known_not_exported)

    def test_secrets(self):
        known_not_exported = {
            'buildbot.secrets.manager.SecretManager',
            'buildbot.secrets.providers.base.SecretProviderBase',
            'buildbot.secrets.secret.SecretDetails',
        }
        self.verify_plugins_registered('secrets', 'buildbot.secrets', None, known_not_exported)

    def test_webhooks(self):
        # in the case of webhooks the entry points list modules, not classes, so
        # verify_plugins_registered won't work. For now let's ignore this edge case
        get_plugins('webhooks', None, load_now=True)

    def test_workers(self):
        self.verify_plugins_registered('worker', 'buildbot.worker', IWorker)

    def verify_plugins_registered(self, plugin_type, module_name, interface,
                                  known_not_exported=None):
        # This will verify whether we can load plugins, i.e. whether the entry points are valid.
        plugins = get_plugins(plugin_type, interface, load_now=True)

        # Now verify that are no unregistered plugins left.
        existing_classes = self.get_existing_classes(module_name, interface)

        exported_classes = {'{}.{}'.format(plugins._get_entry(name)._entry.module_name, name)
                            for name in plugins.names}
        if known_not_exported is None:
            known_not_exported = set()

        not_exported_classes = existing_classes - exported_classes - known_not_exported
        self.assertEqual(not_exported_classes, set())
        self.assertEqual(known_not_exported - existing_classes, set())

    def get_existing_classes(self, module_name, interface):
        existing_modules = get_python_module_contents(module_name)
        existing_classes = set()

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            for existing_module in existing_modules:
                module = importlib.import_module(existing_module)
                for name, obj in inspect.getmembers(module):
                    if name.startswith('_'):
                        continue
                    if inspect.isclass(obj) and obj.__module__ == existing_module:
                        if interface is not None and not issubclass(obj, interface):
                            continue
                        existing_classes.add('{}.{}'.format(existing_module, name))
        return existing_classes
