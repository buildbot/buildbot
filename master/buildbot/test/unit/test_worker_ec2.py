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
# Portions Copyright Buildbot Team Members
# Portions Copyright 2014 Longaccess private company

from twisted.trial import unittest

from buildbot.test.util.warnings import assertNotProducesWarnings
from buildbot.test.util.warnings import assertProducesWarning
from buildbot.test.util.warnings import assertProducesWarnings
from buildbot.worker_transition import DeprecatedWorkerNameWarning

try:
    from moto import mock_ec2
    assert mock_ec2
    import boto
    assert boto
except ImportError:
    boto = None
    ec2 = None


if boto is not None:
    from buildbot.worker import ec2


# redefine the mock_ec2 decorator to skip the test if boto or moto
# isn't installed
def skip_ec2(f):
    f.skip = "boto or moto is not installed"
    return f
if boto is None:
    mock_ec2 = skip_ec2


class TestEC2LatentWorker(unittest.TestCase):
    ec2_connection = None

    def setUp(self):
        super(TestEC2LatentWorker, self).setUp()
        if boto is None:
            raise unittest.SkipTest("moto not found")

    def botoSetup(self, name='latent_buildbot_worker'):
        c = boto.connect_ec2()
        try:
            c.create_key_pair(name)
        except NotImplementedError:
            raise unittest.SkipTest("KeyPairs.create_key_pair not implemented"
                                    " in this version of moto, please update.")
        c.create_security_group(name, 'the security group')
        instance = c.run_instances('foo').instances[0]
        c.create_image(instance.id, "foo", "bar")
        c.terminate_instances([instance.id])
        return c

    @mock_ec2
    def test_constructor_minimal(self):
        c = self.botoSetup('latent_buildbot_slave')
        amis = c.get_all_images()
        with assertProducesWarnings(
                DeprecatedWorkerNameWarning,
                messages_patterns=[
                    r"Use of default value of 'keypair_name' of "
                    r"EC2LatentWorker constructor is deprecated",
                    r"Use of default value of 'security_name' of "
                    r"EC2LatentWorker constructor is deprecated"
                ]):
            bs = ec2.EC2LatentWorker('bot1', 'sekrit', 'm1.large',
                                     identifier='publickey',
                                     secret_identifier='privatekey',
                                     ami=amis[0].id
                                     )
        self.assertEqual(bs.workername, 'bot1')
        self.assertEqual(bs.password, 'sekrit')
        self.assertEqual(bs.instance_type, 'm1.large')
        self.assertEqual(bs.ami, amis[0].id)

    @mock_ec2
    def test_constructor_tags(self):
        c = self.botoSetup('latent_buildbot_slave')
        amis = c.get_all_images()
        tags = {'foo': 'bar'}
        with assertProducesWarnings(
                DeprecatedWorkerNameWarning,
                messages_patterns=[
                    r"Use of default value of 'keypair_name' of "
                    r"EC2LatentWorker constructor is deprecated",
                    r"Use of default value of 'security_name' of "
                    r"EC2LatentWorker constructor is deprecated"
                ]):
            bs = ec2.EC2LatentWorker('bot1', 'sekrit', 'm1.large',
                                     identifier='publickey',
                                     secret_identifier='privatekey',
                                     tags=tags,
                                     ami=amis[0].id
                                     )
        self.assertEqual(bs.tags, tags)

    @mock_ec2
    def test_fail_mixing_classic_and_vpc_ec2_settings(self):
        c = self.botoSetup()
        amis = c.get_all_images()

        def create_worker():
            ec2.EC2LatentWorker('bot1', 'sekrit', 'm1.large',
                                keypair_name="test_key",
                                identifier='publickey',
                                secret_identifier='privatekey',
                                ami=amis[0].id,
                                security_name="classic",
                                subnet_id="sn-1234"
                                )

        self.assertRaises(ValueError, create_worker)

    @mock_ec2
    def test_start_vpc_instance(self):
        c = self.botoSetup()

        vpc_conn = boto.connect_vpc()
        vpc = vpc_conn.create_vpc("192.168.0.0/24")
        subnet = vpc_conn.create_subnet(vpc.id, "192.168.0.0/24")
        amis = c.get_all_images()

        sg = c.create_security_group("test_sg", "test_sg", vpc.id)
        bs = ec2.EC2LatentWorker('bot1', 'sekrit', 'm1.large',
                                 identifier='publickey',
                                 secret_identifier='privatekey',
                                 keypair_name="latent_buildbot_worker",
                                 security_group_ids=[sg.id],
                                 subnet_id=subnet.id,
                                 ami=amis[0].id
                                 )

        instance_id, _, _ = bs._start_instance()
        instances = [i for i in c.get_only_instances()
                     if i.state != "terminated"]

        self.assertEqual(len(instances), 1)
        self.assertEqual(instances[0].id, instance_id)
        self.assertEqual(instances[0].subnet_id, subnet.id)
        self.assertEqual(len(instances[0].groups), 1)
        self.assertEqual(instances[0].groups[0].id, sg.id)
        self.assertEqual(instances[0].key_name, 'latent_buildbot_worker')

    @mock_ec2
    def test_start_instance(self):
        c = self.botoSetup('latent_buildbot_slave')
        amis = c.get_all_images()
        with assertProducesWarnings(
                DeprecatedWorkerNameWarning,
                messages_patterns=[
                    r"Use of default value of 'keypair_name' of "
                    r"EC2LatentWorker constructor is deprecated",
                    r"Use of default value of 'security_name' of "
                    r"EC2LatentWorker constructor is deprecated"
                ]):
            bs = ec2.EC2LatentWorker('bot1', 'sekrit', 'm1.large',
                                     identifier='publickey',
                                     secret_identifier='privatekey',
                                     ami=amis[0].id
                                     )
        instance_id, image_id, start_time = bs._start_instance()
        self.assertTrue(instance_id.startswith('i-'))
        self.assertTrue(image_id.startswith('r-'))
        self.assertTrue(start_time > 0)
        instances = [i for i in c.get_only_instances()
                     if i.state != "terminated"]
        self.assertEqual(len(instances), 1)
        self.assertEqual(instances[0].id, instance_id)
        self.assertEqual(instances[0].tags, {})

    @mock_ec2
    def test_start_instance_volumes(self):
        c = self.botoSetup('latent_buildbot_slave')
        amis = c.get_all_images()
        with assertProducesWarnings(
                DeprecatedWorkerNameWarning,
                messages_patterns=[
                    r"Use of default value of 'keypair_name' of "
                    r"EC2LatentWorker constructor is deprecated",
                    r"Use of default value of 'security_name' of "
                    r"EC2LatentWorker constructor is deprecated"
                ]):
            bs = ec2.EC2LatentWorker('bot1', 'sekrit', 'm1.large',
                                     identifier='publickey',
                                     secret_identifier='privatekey',
                                     ami=amis[0].id,
                                     block_device_map={
                                         "/dev/xvdb": {
                                             "volume_type": "io1",
                                             "iops": 10,
                                             "size": 20,
                                         },
                                         "/dev/xvdc": {
                                             "volume_type": "gp2",
                                             "size": 30,
                                             "delete_on_termination": False
                                         }
                                     }
                                     )

        # moto does not currently map volumes properly.  below ensures
        # that my conversion code properly composes it, including
        # delete_on_termination default.
        from boto.ec2.blockdevicemapping import BlockDeviceType
        self.assertEqual(
            set(['/dev/xvdb', '/dev/xvdc']), set(bs.block_device_map.keys()))

        def assertBlockDeviceEqual(a, b):
            self.assertEqual(a.volume_type, b.volume_type)
            self.assertEqual(a.iops, b.iops)
            self.assertEqual(a.size, b.size)
            self.assertEqual(a.delete_on_termination, b.delete_on_termination)

        assertBlockDeviceEqual(
            BlockDeviceType(
                volume_type='io1', iops=10, size=20, delete_on_termination=True),
            bs.block_device_map['/dev/xvdb'])

        assertBlockDeviceEqual(
            BlockDeviceType(
                volume_type='gp2', size=30, delete_on_termination=False),
            bs.block_device_map['/dev/xvdc'])

    @mock_ec2
    def test_start_instance_attach_volume(self):
        c = self.botoSetup()
        vol = c.create_volume('10', 'us-east-1a')
        amis = c.get_all_images()
        ami = amis[0]
        bs = ec2.EC2LatentWorker('bot1', 'sekrit', 'm1.large',
                                 identifier='publickey',
                                 secret_identifier='privatekey',
                                 keypair_name="latent_buildbot_worker",
                                 security_name='latent_buildbot_worker',
                                 ami=ami.id,
                                 volumes=[(vol.id, "/dev/sdz")]
                                 )
        id, _, _ = bs._start_instance()
        instances = [i for i in c.get_only_instances()
                     if i.state != "terminated"]
        instance = instances[0]
        self.assertEqual(
            vol.id, instance.block_device_mapping['/dev/sdz'].volume_id)

    @mock_ec2
    def test_start_instance_tags(self):
        c = self.botoSetup('latent_buildbot_slave')
        amis = c.get_all_images()
        tags = {'foo': 'bar'}
        with assertProducesWarnings(
                DeprecatedWorkerNameWarning,
                messages_patterns=[
                    r"Use of default value of 'keypair_name' of "
                    r"EC2LatentWorker constructor is deprecated",
                    r"Use of default value of 'security_name' of "
                    r"EC2LatentWorker constructor is deprecated"
                ]):
            bs = ec2.EC2LatentWorker('bot1', 'sekrit', 'm1.large',
                                     identifier='publickey',
                                     secret_identifier='privatekey',
                                     tags=tags,
                                     ami=amis[0].id
                                     )
        id, _, _ = bs._start_instance()
        instances = [i for i in c.get_only_instances()
                     if i.state != "terminated"]
        self.assertEqual(len(instances), 1)
        self.assertEqual(instances[0].id, id)
        self.assertEqual(instances[0].tags, tags)

    @mock_ec2
    def test_start_instance_ip(self):
        c = self.botoSetup()
        amis = c.get_all_images()
        eip = c.allocate_address(domain='vpc')
        elastic_ip = eip.public_ip
        bs = ec2.EC2LatentWorker('bot1', 'sekrit', 'm1.large',
                                 identifier='publickey',
                                 secret_identifier='privatekey',
                                 keypair_name="latent_buildbot_worker",
                                 security_name='latent_buildbot_worker',
                                 elastic_ip=elastic_ip,
                                 ami=amis[0].id
                                 )
        id, _, _ = bs._start_instance()
        instances = [i for i in c.get_only_instances()
                     if i.state != "terminated"]
        addresses = c.get_all_addresses()
        self.assertEqual(instances[0].id, addresses[0].instance_id)

    @mock_ec2
    def test_start_vpc_spot_instance(self):
        c = self.botoSetup()

        vpc_conn = boto.connect_vpc()
        vpc = vpc_conn.create_vpc("192.168.0.0/24")
        subnet = vpc_conn.create_subnet(vpc.id, "192.168.0.0/24")
        amis = c.get_all_images()

        sg = c.create_security_group("test_sg", "test_sg", vpc.id)

        bs = ec2.EC2LatentWorker('bot1', 'sekrit', 'm1.large',
                                 identifier='publickey',
                                 secret_identifier='privatekey',
                                 keypair_name="latent_buildbot_worker",
                                 ami=amis[0].id, spot_instance=True,
                                 max_spot_price=1.5,
                                 security_group_ids=[sg.id],
                                 subnet_id=subnet.id,
                                 )

        instance_id, _, _ = bs._start_instance()
        instances = [i for i in c.get_only_instances()
                     if i.state != "terminated"]

        self.assertTrue(bs.spot_instance)
        self.assertEqual(len(instances), 1)
        self.assertEqual(instances[0].id, instance_id)
        self.assertEqual(instances[0].subnet_id, subnet.id)
        self.assertEqual(len(instances[0].groups), 1)
        self.assertEqual(instances[0].groups[0].id, sg.id)

    @mock_ec2
    def test_start_spot_instance(self):
        c = self.botoSetup('latent_buildbot_slave')
        amis = c.get_all_images()
        product_description = 'Linux/Unix'
        with assertProducesWarnings(
                DeprecatedWorkerNameWarning,
                messages_patterns=[
                    r"Use of default value of 'keypair_name' of "
                    r"EC2LatentWorker constructor is deprecated",
                    r"Use of default value of 'security_name' of "
                    r"EC2LatentWorker constructor is deprecated"
                ]):
            bs = ec2.EC2LatentWorker('bot1', 'sekrit', 'm1.large',
                                     identifier='publickey',
                                     secret_identifier='privatekey',
                                     ami=amis[0].id, spot_instance=True,
                                     max_spot_price=1.5,
                                     product_description=product_description
                                     )
        instance_id, _, _ = bs._start_instance()
        instances = [i for i in c.get_only_instances()
                     if i.state != "terminated"]
        self.assertTrue(bs.spot_instance)
        self.assertEqual(bs.retry, 1)
        self.assertEqual(bs.product_description, product_description)
        self.assertEqual(len(instances), 1)
        self.assertEqual(instances[0].id, instance_id)
        self.assertEqual(instances[0].tags, {})

    @mock_ec2
    def test_start_spot_instance_retry(self):
        c = self.botoSetup('latent_buildbot_slave')
        amis = c.get_all_images()
        product_description = 'Linux/Unix'
        retry = 3
        with assertProducesWarnings(
                DeprecatedWorkerNameWarning,
                messages_patterns=[
                    r"Use of default value of 'keypair_name' of "
                    r"EC2LatentWorker constructor is deprecated",
                    r"Use of default value of 'security_name' of "
                    r"EC2LatentWorker constructor is deprecated"
                ]):
            bs = ec2.EC2LatentWorker('bot1', 'sekrit', 'm1.large',
                                     identifier='publickey',
                                     secret_identifier='privatekey',
                                     ami=amis[0].id, retry=retry,
                                     spot_instance=True, max_spot_price=1.5,
                                     product_description=product_description
                                     )
        id, _, _ = bs._start_instance()
        instances = [i for i in c.get_only_instances()
                     if i.state != "terminated"]
        self.assertTrue(bs.spot_instance)
        self.assertEqual(bs.retry, 3)
        self.assertEqual(bs.attempt, 1)
        self.assertEqual(len(instances), 1)
        self.assertEqual(instances[0].id, id)

    @mock_ec2
    def test_get_image_ami(self):
        c = self.botoSetup()
        amis = c.get_all_images()
        ami = amis[0]
        bs = ec2.EC2LatentWorker('bot1', 'sekrit', 'm1.large',
                                 identifier='publickey',
                                 secret_identifier='privatekey',
                                 keypair_name="latent_buildbot_worker",
                                 security_name='latent_buildbot_worker',
                                 ami=ami.id
                                 )
        image = bs.get_image()

        self.assertEqual(image.id, ami.id)

    @mock_ec2
    def test_get_image_owners(self):
        c = self.botoSetup()
        amis = c.get_all_images()
        ami = amis[0]
        bs = ec2.EC2LatentWorker('bot1', 'sekrit', 'm1.large',
                                 identifier='publickey',
                                 secret_identifier='privatekey',
                                 keypair_name="latent_buildbot_worker",
                                 security_name='latent_buildbot_worker',
                                 valid_ami_owners=[int(ami.ownerId)]
                                 )
        image = bs.get_image()

        self.assertEqual(image.id, ami.id)

    @mock_ec2
    def test_get_image_location(self):
        c = self.botoSetup()
        amis = c.get_all_images()
        ami = amis[0]
        bs = ec2.EC2LatentWorker('bot1', 'sekrit', 'm1.large',
                                 identifier='publickey',
                                 secret_identifier='privatekey',
                                 keypair_name="latent_buildbot_worker",
                                 security_name='latent_buildbot_worker',
                                 valid_ami_location_regex='amazon/.*'
                                 )
        image = bs.get_image()

        self.assertEqual(image.id, ami.id)

    @mock_ec2
    def test_get_image_location_not_found(self):
        self.botoSetup()

        def create_worker():
            ec2.EC2LatentWorker('bot1', 'sekrit', 'm1.large',
                                identifier='publickey',
                                secret_identifier='privatekey',
                                keypair_name="latent_buildbot_worker",
                                security_name='latent_buildbot_worker',
                                valid_ami_location_regex='foobar.*'
                                )

        self.assertRaises(ValueError, create_worker)

    @mock_ec2
    def test_start_spot_instance_retry_low_price(self):
        '''
        This test should attempt to start an instance that will be rejected with
        price-too-low. At this point, the ec2 worker code should increment
        bs.attempt and multiply the price by bs.retry_price_adjustment. This
        should continue for bs.retry iterations or until the spot request is
        accepted.
        '''
        raise unittest.SkipTest("Requires un-released functionality in moto.")


class TestEC2LatentWorkerDefaultKeyairSecurityGroup(unittest.TestCase):
    ec2_connection = None

    def setUp(self):
        super(TestEC2LatentWorkerDefaultKeyairSecurityGroup, self).setUp()
        if boto is None:
            raise unittest.SkipTest("moto not found")

    def botoSetup(self):
        c = boto.connect_ec2()
        try:
            c.create_key_pair('latent_buildbot_slave')
            c.create_key_pair('test_keypair')
        except NotImplementedError:
            raise unittest.SkipTest("KeyPairs.create_key_pair not implemented"
                                    " in this version of moto, please update.")
        c.create_security_group('latent_buildbot_slave', 'the security group')
        c.create_security_group('test_security_group', 'other security group')
        instance = c.run_instances('foo').instances[0]
        c.create_image(instance.id, "foo", "bar")
        c.terminate_instances([instance.id])
        return c

    @mock_ec2
    def test_use_of_default_keypair_security_warning(self):
        c = self.botoSetup()
        amis = c.get_all_images()
        with assertProducesWarnings(
                DeprecatedWorkerNameWarning,
                messages_patterns=[
                    r"Use of default value of 'keypair_name' of "
                    r"EC2LatentWorker constructor is deprecated",
                    r"Use of default value of 'security_name' of "
                    r"EC2LatentWorker constructor is deprecated"
                ]):
            bs = ec2.EC2LatentWorker('bot1', 'sekrit', 'm1.large',
                                     identifier='publickey',
                                     secret_identifier='privatekey',
                                     ami=amis[0].id
                                     )
        self.assertEqual(bs.keypair_name, 'latent_buildbot_slave')
        self.assertEqual(bs.security_name, 'latent_buildbot_slave')

    @mock_ec2
    def test_use_of_default_keypair_warning(self):
        c = self.botoSetup()
        amis = c.get_all_images()
        with assertProducesWarnings(
                DeprecatedWorkerNameWarning,
                messages_patterns=[
                    r"Use of default value of 'keypair_name' of "
                    r"EC2LatentWorker constructor is deprecated",
                ]):
            bs = ec2.EC2LatentWorker('bot1', 'sekrit', 'm1.large',
                                     identifier='publickey',
                                     secret_identifier='privatekey',
                                     ami=amis[0].id,
                                     security_name='test_security_group',
                                     )
        self.assertEqual(bs.keypair_name, 'latent_buildbot_slave')
        self.assertEqual(bs.security_name, 'test_security_group')

    @mock_ec2
    def test_use_of_default_security_warning(self):
        c = self.botoSetup()
        amis = c.get_all_images()
        with assertProducesWarnings(
                DeprecatedWorkerNameWarning,
                messages_patterns=[
                    r"Use of default value of 'security_name' of "
                    r"EC2LatentWorker constructor is deprecated",
                ]):
            bs = ec2.EC2LatentWorker('bot1', 'sekrit', 'm1.large',
                                     identifier='publickey',
                                     secret_identifier='privatekey',
                                     ami=amis[0].id,
                                     keypair_name='test_keypair',
                                     )
        self.assertEqual(bs.keypair_name, 'test_keypair')
        self.assertEqual(bs.security_name, 'latent_buildbot_slave')

    @mock_ec2
    def test_no_default_security_warning_when_security_group_ids(self):
        c = self.botoSetup()
        amis = c.get_all_images()

        bs = ec2.EC2LatentWorker('bot1', 'sekrit', 'm1.large',
                                 identifier='publickey',
                                 secret_identifier='privatekey',
                                 ami=amis[0].id,
                                 keypair_name='test_keypair',
                                 subnet_id=["sn-1"]
                                 )
        self.assertEqual(bs.security_name, None)

    @mock_ec2
    def test_use_non_default_keypair_security(self):
        c = self.botoSetup()
        amis = c.get_all_images()
        with assertNotProducesWarnings(DeprecatedWorkerNameWarning):
            bs = ec2.EC2LatentWorker('bot1', 'sekrit', 'm1.large',
                                     identifier='publickey',
                                     secret_identifier='privatekey',
                                     ami=amis[0].id,
                                     security_name='test_security_group',
                                     keypair_name='test_keypair',
                                     )
        self.assertEqual(bs.keypair_name, 'test_keypair')
        self.assertEqual(bs.security_name, 'test_security_group')


class TestWorkerTransition(unittest.TestCase):

    def test_EC2LatentBuildSlave_deprecated(self):
        from buildbot.worker.ec2 import EC2LatentWorker

        with assertProducesWarning(
                DeprecatedWorkerNameWarning,
                message_pattern="EC2LatentBuildSlave was deprecated"):
            from buildbot.buildslave.ec2 import EC2LatentBuildSlave

        self.assertIdentical(EC2LatentBuildSlave, EC2LatentWorker)
