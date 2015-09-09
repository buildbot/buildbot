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

try:
    from moto import mock_ec2
    assert mock_ec2
    import boto
    assert boto
except ImportError:
    boto = None
    ec2 = None

if boto is not None:
    from buildbot.buildworker import ec2

from twisted.trial import unittest


# redefine the mock_ec2 decorator to skip the test if boto isn't installed
def skip_ec2(f):
    f.skip = "boto not installed"
    return f
if boto is None:
    mock_ec2 = skip_ec2


class TestEC2LatentBuildWorker(unittest.TestCase):
    ec2_connection = None

    def setUp(self):
        super(TestEC2LatentBuildWorker, self).setUp()
        if boto is None:
            raise unittest.SkipTest("moto not found")

    def botoSetup(self):
        c = boto.connect_ec2()
        try:
            c.create_key_pair('latent_buildbot_worker')
        except NotImplementedError:
            raise unittest.SkipTest("KeyPairs.create_key_pair not implemented"
                                    " in this version of moto, please update.")
        c.create_security_group('latent_buildbot_worker', 'the security group')
        instance = c.run_instances('foo').instances[0]
        c.create_image(instance.id, "foo", "bar")
        c.terminate_instances([instance.id])
        return c

    @mock_ec2
    def test_constructor_minimal(self):
        c = self.botoSetup()
        amis = c.get_all_images()
        bs = ec2.EC2LatentBuildWorker('bot1', 'sekrit', 'm1.large',
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
        c = self.botoSetup()
        amis = c.get_all_images()
        tags = {'foo': 'bar'}
        bs = ec2.EC2LatentBuildWorker('bot1', 'sekrit', 'm1.large',
                                     identifier='publickey',
                                     secret_identifier='privatekey',
                                     tags=tags,
                                     ami=amis[0].id
                                      )
        self.assertEqual(bs.tags, tags)

    @mock_ec2
    def test_start_instance(self):
        c = self.botoSetup()
        amis = c.get_all_images()
        bs = ec2.EC2LatentBuildWorker('bot1', 'sekrit', 'm1.large',
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
    def test_start_instance_tags(self):
        c = self.botoSetup()
        amis = c.get_all_images()
        tags = {'foo': 'bar'}
        bs = ec2.EC2LatentBuildWorker('bot1', 'sekrit', 'm1.large',
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
    def test_start_spot_instance(self):
        c = self.botoSetup()
        amis = c.get_all_images()
        product_description = 'Linux/Unix'
        bs = ec2.EC2LatentBuildWorker('bot1', 'sekrit', 'm1.large',
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
        c = self.botoSetup()
        amis = c.get_all_images()
        product_description = 'Linux/Unix'
        retry = 3
        bs = ec2.EC2LatentBuildWorker('bot1', 'sekrit', 'm1.large',
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
    def test_start_spot_instance_retry_low_price(self):
        '''
        This test should attempt to start an instance that will be rejected with
        price-too-low. At this point, the ec2 buildworker code should increment
        bs.attempt and multiply the price by bs.retry_price_adjustment. This
        should continue for bs.retry iterations or until the spot request is
        accepted.
        '''
        raise unittest.SkipTest("Requires un-released functionality in moto.")
