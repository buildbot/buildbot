# Portions copyright Canonical Ltd. 2009

import os
import sys
import StringIO
import textwrap

from twisted.trial import unittest
from twisted.internet import defer, reactor

from buildbot.process.base import BuildRequest
from buildbot.sourcestamp import SourceStamp
from buildbot.status.builder import SUCCESS
from buildbot.test.runutils import RunMixin


PENDING = 'pending'
RUNNING = 'running'
SHUTTINGDOWN = 'shutting-down'
TERMINATED = 'terminated'


class EC2ResponseError(Exception):
    def __init__(self, code):
        self.code = code


class Stub:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class Instance:

    def __init__(self, data, ami, **kwargs):
        self.data = data
        self.state = PENDING
        self.id = ami
        self.public_dns_name = 'ec2-012-345-678-901.compute-1.amazonaws.com'
        self.__dict__.update(kwargs)
        self.output = Stub(name='output', output='example_output')

    def update(self):
        if self.state == PENDING:
            self.data.testcase.connectOneSlave(self.data.slave.slavename)
            self.state = RUNNING
        elif self.state == SHUTTINGDOWN:
            slavename = self.data.slave.slavename
            slaves = self.data.testcase.slaves
            if slavename in slaves:
                def discard(data):
                    pass
                s = slaves.pop(slavename)
                bot = s.getServiceNamed("bot")
                for buildername in self.data.slave.slavebuilders:
                    remote = bot.builders[buildername].remote
                    if remote is None:
                        continue
                    broker = remote.broker
                    broker.dataReceived = discard # seal its ears
                    # and take away its voice
                    broker.transport.write = discard
                # also discourage it from reconnecting once the connection
                # goes away
                s.bf.continueTrying = False
                # stop the service for cleanliness
                s.stopService()
            self.state = TERMINATED

    def get_console_output(self):
        return self.output

    def use_ip(self, elastic_ip):
        if isinstance(elastic_ip, Stub):
            elastic_ip = elastic_ip.public_ip
        if self.data.addresses[elastic_ip] is not None:
            raise ValueError('elastic ip already used')
        self.data.addresses[elastic_ip] = self

    def stop(self):
        self.state = SHUTTINGDOWN

class Image:

    def __init__(self, data, ami, owner, location):
        self.data = data
        self.id = ami
        self.owner = owner
        self.location = location

    def run(self, **kwargs):
        return Stub(name='reservation',
                    instances=[Instance(self.data, self.id, **kwargs)])

    def create(klass, data, ami, owner, location):
        assert ami not in data.images
        self = klass(data, ami, owner, location)
        data.images[ami] = self
        return self
    create = classmethod(create)


class Connection:

    def __init__(self, data):
        self.data = data

    def get_all_key_pairs(self, keypair_name):
        try:
            return [self.data.keys[keypair_name]]
        except KeyError:
            raise EC2ResponseError('InvalidKeyPair.NotFound')

    def create_key_pair(self, keypair_name):
        return Key.create(keypair_name, self.data.keys)

    def get_all_security_groups(self, security_name):
        try:
            return [self.data.security_groups[security_name]]
        except KeyError:
            raise EC2ResponseError('InvalidGroup.NotFound')

    def create_security_group(self, security_name, description):
        assert security_name not in self.data.security_groups
        res = Stub(name='security_group', value=security_name,
                   description=description)
        self.data.security_groups[security_name] = res
        return res

    def get_all_images(self, owners=None):
        # return a list of images.  images have .location and .id.
        res = self.data.images.values()
        if owners:
            res = [image for image in res if image.owner in owners]
        return res

    def get_image(self, machine_id):
        # return image or raise an error
        return self.data.images[machine_id]

    def get_all_addresses(self, elastic_ips):
        res = []
        for ip in elastic_ips:
            if ip in self.data.addresses:
                res.append(Stub(public_ip=ip))
            else:
                raise EC2ResponseError('...bad address...')
        return res

    def disassociate_address(self, address):
        if address not in self.data.addresses:
            raise EC2ResponseError('...unknown address...')
        self.data.addresses[address] = None


class Key:

    # this is what we would need to do if we actually needed a real key.
    # We don't right now.
    #def __init__(self):
    #    self.raw = paramiko.RSAKey.generate(256)
    #    f = StringIO.StringIO()
    #    self.raw.write_private_key(f)
    #    self.material = f.getvalue()

    def create(klass, name, keys):
        self = klass()
        self.name = name
        self.keys = keys
        assert name not in keys
        keys[name] = self
        return self
    create = classmethod(create)

    def delete(self):
        del self.keys[self.name]


class Boto:

    slave = None # must be set in setUp

    def __init__(self, testcase):
        self.testcase = testcase
        self.keys = {}
        Key.create('latent_buildbot_slave', self.keys)
        Key.create('buildbot_slave', self.keys)
        kk = self.keys.keys()
        kk.sort()
        assert kk == ['buildbot_slave', 'latent_buildbot_slave']
        self.original_keys = dict(self.keys)
        self.security_groups = {
            'latent_buildbot_slave': Stub(name='security_group',
                                          value='latent_buildbot_slave')}
        self.addresses = {'127.0.0.1': None}
        self.images = {}
        Image.create(self, 'ami-12345', 12345667890,
                     'test-xx/image.manifest.xml')
        Image.create(self, 'ami-AF000', 11111111111,
                     'test-f0a/image.manifest.xml')
        Image.create(self, 'ami-CE111', 22222222222,
                     'test-e1b/image.manifest.xml')
        Image.create(self, 'ami-ED222', 22222222222,
                     'test-d2c/image.manifest.xml')
        Image.create(self, 'ami-FC333', 22222222222,
                     'test-c30d/image.manifest.xml')
        Image.create(self, 'ami-DB444', 11111111111,
                     'test-b4e/image.manifest.xml')
        Image.create(self, 'ami-BA555', 11111111111,
                     'test-a5f/image.manifest.xml')

    def connect_ec2(self, identifier, secret_identifier):
        assert identifier == 'publickey', identifier
        assert secret_identifier == 'privatekey', secret_identifier
        return Connection(self)

    exception = Stub(EC2ResponseError=EC2ResponseError)


class Mixin(RunMixin):

    def doBuild(self):
        br = BuildRequest("forced", SourceStamp(), 'test_builder')
        d = br.waitUntilFinished()
        self.control.getBuilder('b1').requestBuild(br)
        return d

    def setUp(self):
        self.boto_setUp1()
        self.master.loadConfig(self.config)
        self.boto_setUp2()
        self.boto_setUp3()

    def boto_setUp1(self):
        # debugging
        #import twisted.internet.base
        #twisted.internet.base.DelayedCall.debug = True
        # debugging
        RunMixin.setUp(self)
        self.boto = boto = Boto(self)
        if 'boto' not in sys.modules:
            sys.modules['boto'] = boto
            sys.modules['boto.exception'] = boto.exception
        if 'buildbot.ec2buildslave' in sys.modules:
            sys.modules['buildbot.ec2buildslave'].boto = boto

    def boto_setUp2(self):
        if sys.modules['boto'] is self.boto:
            del sys.modules['boto']
            del sys.modules['boto.exception']

    def boto_setUp3(self):
        self.master.startService()
        self.boto.slave = self.bot1 = self.master.botmaster.slaves['bot1']
        self.bot1._poll_resolution = 0.1
        self.b1 = self.master.botmaster.builders['b1']

    def tearDown(self):
        try:
            import boto
            import boto.exception
        except ImportError:
            pass
        else:
            sys.modules['buildbot.ec2buildslave'].boto = boto
        return RunMixin.tearDown(self)


class BasicConfig(Mixin, unittest.TestCase):
    config = textwrap.dedent("""\
        from buildbot.process import factory
        from buildbot.steps import dummy
        from buildbot.ec2buildslave import EC2LatentBuildSlave
        from buildbot.config import BuilderConfig
        s = factory.s

        BuildmasterConfig = c = {}
        c['slaves'] = [EC2LatentBuildSlave('bot1', 'sekrit', 'm1.large',
                                           'ami-12345',
                                           identifier='publickey',
                                           secret_identifier='privatekey'
                                           )]
        c['schedulers'] = []
        c['slavePortnum'] = 0
        c['schedulers'] = []

        f1 = factory.BuildFactory([s(dummy.RemoteDummy, timeout=1)])

        c['builders'] = [
            BuilderConfig(name='b1', slavename='bot1', factory=f1),
        ]
        """)

    def testSequence(self):
        # test with secrets in config, a single AMI, and defaults/
        self.assertEqual(self.bot1.ami, 'ami-12345')
        self.assertEqual(self.bot1.instance_type, 'm1.large')
        self.assertEqual(self.bot1.keypair_name, 'latent_buildbot_slave')
        self.assertEqual(self.bot1.security_name, 'latent_buildbot_slave')
        # this would be appropriate if we were recreating keys.
        #self.assertNotEqual(self.boto.keys['latent_buildbot_slave'],
        #                    self.boto.original_keys['latent_buildbot_slave'])
        self.failUnless(isinstance(self.bot1.get_image(), Image))
        self.assertEqual(self.bot1.get_image().id, 'ami-12345')
        self.assertIdentical(self.bot1.elastic_ip, None)
        self.assertIdentical(self.bot1.instance, None)
        # let's start a build...
        self.build_deferred = self.doBuild()
        # ...and wait for the ec2 slave to show up
        d = self.bot1.substantiation_deferred
        d.addCallback(self._testSequence_1)
        return d
    def _testSequence_1(self, res):
        # bot 1 is substantiated.
        self.assertNotIdentical(self.bot1.slave, None)
        self.failUnless(self.bot1.substantiated)
        self.failUnless(isinstance(self.bot1.instance, Instance))
        self.assertEqual(self.bot1.instance.id, 'ami-12345')
        self.assertEqual(self.bot1.instance.state, RUNNING)
        self.assertEqual(self.bot1.instance.key_name, 'latent_buildbot_slave')
        self.assertEqual(self.bot1.instance.security_groups,
                         ['latent_buildbot_slave'])
        self.assertEqual(self.bot1.instance.instance_type, 'm1.large')
        self.assertEqual(self.bot1.output.output, 'example_output')
        # now we'll wait for the build to complete
        d = self.build_deferred
        del self.build_deferred
        d.addCallback(self._testSequence_2)
        return d
    def _testSequence_2(self, res):
        # build was a success!
        self.failUnlessEqual(res.getResults(), SUCCESS)
        self.failUnlessEqual(res.getSlavename(), "bot1")
        # Let's let it shut down.  We'll set the build_wait_timer to fire
        # sooner, and wait for it to fire.
        self.bot1.build_wait_timer.reset(0)
        # we'll stash the instance around to look at it
        self.instance = self.bot1.instance
        # now we wait.
        d = defer.Deferred()
        reactor.callLater(0.5, d.callback, None)
        d.addCallback(self._testSequence_3)
        return d
    def _testSequence_3(self, res):
        # slave is insubstantiated
        self.assertIdentical(self.bot1.slave, None)
        self.failIf(self.bot1.substantiated)
        self.assertIdentical(self.bot1.instance, None)
        self.assertEqual(self.instance.state, TERMINATED)
        del self.instance

class ElasticIP(Mixin, unittest.TestCase):
    config = textwrap.dedent("""\
        from buildbot.process import factory
        from buildbot.steps import dummy
        from buildbot.ec2buildslave import EC2LatentBuildSlave
        from buildbot.config import BuilderConfig
        s = factory.s

        BuildmasterConfig = c = {}
        c['slaves'] = [EC2LatentBuildSlave('bot1', 'sekrit', 'm1.large',
                                           'ami-12345',
                                           identifier='publickey',
                                           secret_identifier='privatekey',
                                           elastic_ip='127.0.0.1'
                                           )]
        c['schedulers'] = []
        c['slavePortnum'] = 0
        c['schedulers'] = []

        f1 = factory.BuildFactory([s(dummy.RemoteDummy, timeout=1)])

        c['builders'] = [
            BuilderConfig(name='b1', slavename='bot1', factory=f1),
        ]
        """)

    def testSequence(self):
        self.assertEqual(self.bot1.elastic_ip.public_ip, '127.0.0.1')
        self.assertIdentical(self.boto.addresses['127.0.0.1'], None)
        # let's start a build...
        d = self.doBuild()
        d.addCallback(self._testSequence_1)
        return d
    def _testSequence_1(self, res):
        # build was a success!
        self.failUnlessEqual(res.getResults(), SUCCESS)
        self.failUnlessEqual(res.getSlavename(), "bot1")
        # we have our address
        self.assertIdentical(self.boto.addresses['127.0.0.1'],
                             self.bot1.instance)
        # Let's let it shut down.  We'll set the build_wait_timer to fire
        # sooner, and wait for it to fire.
        self.bot1.build_wait_timer.reset(0)
        d = defer.Deferred()
        reactor.callLater(0.5, d.callback, None)
        d.addCallback(self._testSequence_2)
        return d
    def _testSequence_2(self, res):
        # slave is insubstantiated
        self.assertIdentical(self.bot1.slave, None)
        self.failIf(self.bot1.substantiated)
        self.assertIdentical(self.bot1.instance, None)
        # the address is free again
        self.assertIdentical(self.boto.addresses['127.0.0.1'], None)


class Initialization(Mixin, unittest.TestCase):

    def setUp(self):
        self.boto_setUp1()

    def tearDown(self):
        self.boto_setUp2()
        return Mixin.tearDown(self)

    def testDefaultSeparateFile(self):
        # set up .ec2/aws_id
        home = os.environ['HOME']
        fake_home = os.path.join(os.getcwd(), 'basedir') # see RunMixin.setUp
        os.environ['HOME'] = fake_home
        dir = os.path.join(fake_home, '.ec2')
        os.mkdir(dir)
        f = open(os.path.join(dir, 'aws_id'), 'w')
        f.write('publickey\nprivatekey')
        f.close()
        # The Connection checks the file, so if the secret file is not parsed
        # correctly, *this* is where it would fail. This is the real test.
        from buildbot.ec2buildslave import EC2LatentBuildSlave
        bot1 = EC2LatentBuildSlave('bot1', 'sekrit', 'm1.large',
                                   'ami-12345')
        # for completeness, we'll show that the connection actually exists.
        self.failUnless(isinstance(bot1.conn, Connection))
        # clean up.
        os.environ['HOME'] = home
        self.rmtree(dir)

    def testCustomSeparateFile(self):
        # set up .ec2/aws_id
        file_path = os.path.join(os.getcwd(), 'basedir', 'custom_aws_id')
        f = open(file_path, 'w')
        f.write('publickey\nprivatekey')
        f.close()
        # The Connection checks the file, so if the secret file is not parsed
        # correctly, *this* is where it would fail. This is the real test.
        from buildbot.ec2buildslave import EC2LatentBuildSlave
        bot1 = EC2LatentBuildSlave('bot1', 'sekrit', 'm1.large',
                                   'ami-12345', aws_id_file_path=file_path)
        # for completeness, we'll show that the connection actually exists.
        self.failUnless(isinstance(bot1.conn, Connection))

    def testNoAMIBroken(self):
        # you must specify an AMI, or at least one of valid_ami_owners or
        # valid_ami_location_regex
        from buildbot.ec2buildslave import EC2LatentBuildSlave
        self.assertRaises(ValueError, EC2LatentBuildSlave, 'bot1', 'sekrit',
                          'm1.large', identifier='publickey',
                          secret_identifier='privatekey')

    def testAMIOwnerFilter(self):
        # if you only specify an owner, you get the image owned by any of the
        # owners that sorts last by the AMI's location.
        from buildbot.ec2buildslave import EC2LatentBuildSlave
        bot1 = EC2LatentBuildSlave('bot1', 'sekrit', 'm1.large',
                                   valid_ami_owners=[11111111111],
                                   identifier='publickey',
                                   secret_identifier='privatekey'
                                   )
        self.assertEqual(bot1.get_image().location,
                         'test-f0a/image.manifest.xml')
        bot1 = EC2LatentBuildSlave('bot1', 'sekrit', 'm1.large',
                                   valid_ami_owners=[11111111111,
                                                     22222222222],
                                   identifier='publickey',
                                   secret_identifier='privatekey'
                                   )
        self.assertEqual(bot1.get_image().location,
                         'test-f0a/image.manifest.xml')
        bot1 = EC2LatentBuildSlave('bot1', 'sekrit', 'm1.large',
                                   valid_ami_owners=[22222222222],
                                   identifier='publickey',
                                   secret_identifier='privatekey'
                                   )
        self.assertEqual(bot1.get_image().location,
                         'test-e1b/image.manifest.xml')
        bot1 = EC2LatentBuildSlave('bot1', 'sekrit', 'm1.large',
                                   valid_ami_owners=12345667890,
                                   identifier='publickey',
                                   secret_identifier='privatekey'
                                   )
        self.assertEqual(bot1.get_image().location,
                         'test-xx/image.manifest.xml')

    def testAMISimpleRegexFilter(self):
        from buildbot.ec2buildslave import EC2LatentBuildSlave
        bot1 = EC2LatentBuildSlave(
            'bot1', 'sekrit', 'm1.large',
            valid_ami_location_regex=r'test\-[a-z]\w+/image.manifest.xml',
            identifier='publickey', secret_identifier='privatekey')
        self.assertEqual(bot1.get_image().location,
                         'test-xx/image.manifest.xml')
        bot1 = EC2LatentBuildSlave(
            'bot1', 'sekrit', 'm1.large',
            valid_ami_location_regex=r'test\-[a-z]\d+\w/image.manifest.xml',
            identifier='publickey', secret_identifier='privatekey')
        self.assertEqual(bot1.get_image().location,
                         'test-f0a/image.manifest.xml')
        bot1 = EC2LatentBuildSlave(
            'bot1', 'sekrit', 'm1.large', valid_ami_owners=[22222222222],
            valid_ami_location_regex=r'test\-[a-z]\d+\w/image.manifest.xml',
            identifier='publickey', secret_identifier='privatekey')
        self.assertEqual(bot1.get_image().location,
                         'test-e1b/image.manifest.xml')

    def testAMIRegexAlphaSortFilter(self):
        from buildbot.ec2buildslave import EC2LatentBuildSlave
        bot1 = EC2LatentBuildSlave(
            'bot1', 'sekrit', 'm1.large',
            valid_ami_owners=[11111111111, 22222222222],
            valid_ami_location_regex=r'test\-[a-z]\d+([a-z])/image.manifest.xml',
            identifier='publickey', secret_identifier='privatekey')
        self.assertEqual(bot1.get_image().location,
                         'test-a5f/image.manifest.xml')

    def testAMIRegexIntSortFilter(self):
        from buildbot.ec2buildslave import EC2LatentBuildSlave
        bot1 = EC2LatentBuildSlave(
            'bot1', 'sekrit', 'm1.large',
            valid_ami_owners=[11111111111, 22222222222],
            valid_ami_location_regex=r'test\-[a-z](\d+)[a-z]/image.manifest.xml',
            identifier='publickey', secret_identifier='privatekey')
        self.assertEqual(bot1.get_image().location,
                         'test-c30d/image.manifest.xml')

    def testNewSecurityGroup(self):
        from buildbot.ec2buildslave import EC2LatentBuildSlave
        bot1 = EC2LatentBuildSlave(
            'bot1', 'sekrit', 'm1.large', 'ami-12345',
            identifier='publickey', secret_identifier='privatekey',
            security_name='custom_security_name')
        self.assertEqual(
            self.boto.security_groups['custom_security_name'].value,
            'custom_security_name')
        self.assertEqual(bot1.security_name, 'custom_security_name')

    def testNewKeypairName(self):
        from buildbot.ec2buildslave import EC2LatentBuildSlave
        bot1 = EC2LatentBuildSlave(
            'bot1', 'sekrit', 'm1.large', 'ami-12345',
            identifier='publickey', secret_identifier='privatekey',
            keypair_name='custom_keypair_name')
        self.assertIn('custom_keypair_name', self.boto.keys)
        self.assertEqual(bot1.keypair_name, 'custom_keypair_name')
