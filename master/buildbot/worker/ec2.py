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
# Portions Copyright Canonical Ltd. 2009
"""
A latent worker that uses EC2 to instantiate the workers on demand.

Tested with Python boto 1.5c
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from future.utils import integer_types
from future.utils import iteritems
from future.utils import string_types

import os
import re
import time

from twisted.internet import defer
from twisted.internet import threads
from twisted.python import log

from buildbot import config
from buildbot.interfaces import LatentWorkerFailedToSubstantiate
from buildbot.worker import AbstractLatentWorker
from buildbot.worker_transition import reportDeprecatedWorkerNameUsage

try:
    import boto3
    import botocore
    from botocore.client import ClientError
except ImportError:
    boto3 = None


PENDING = 'pending'
RUNNING = 'running'
SHUTTINGDOWN = 'shutting-down'
TERMINATED = 'terminated'
SPOT_REQUEST_PENDING_STATES = ['pending-evaluation', 'pending-fulfillment']
FULFILLED = 'fulfilled'
PRICE_TOO_LOW = 'price-too-low'


class EC2LatentWorker(AbstractLatentWorker):

    instance = image = None
    _poll_resolution = 5  # hook point for tests

    def __init__(self, name, password, instance_type, ami=None,
                 valid_ami_owners=None, valid_ami_location_regex=None,
                 elastic_ip=None, identifier=None, secret_identifier=None,
                 aws_id_file_path=None, user_data=None, region=None,
                 keypair_name=None,
                 security_name=None,
                 spot_instance=False, max_spot_price=1.6, volumes=None,
                 placement=None, price_multiplier=1.2, tags=None,
                 product_description='Linux/UNIX',
                 subnet_id=None, security_group_ids=None, instance_profile_name=None,
                 block_device_map=None, session=None,
                 **kwargs):

        if not boto3:
            config.error("The python module 'boto3' is needed to use a "
                         "EC2LatentWorker")

        if keypair_name is None:
            reportDeprecatedWorkerNameUsage(
                "Use of default value of 'keypair_name' of EC2LatentWorker "
                "constructor is deprecated. Please explicitly specify value")
            keypair_name = 'latent_buildbot_slave'
        if security_name is None and not subnet_id:
            reportDeprecatedWorkerNameUsage(
                "Use of default value of 'security_name' of EC2LatentWorker "
                "constructor is deprecated. Please explicitly specify value")
            security_name = 'latent_buildbot_slave'

        if volumes is None:
            volumes = []

        if tags is None:
            tags = {}

        AbstractLatentWorker.__init__(self, name, password, **kwargs)

        if security_name and subnet_id:
            raise ValueError(
                'security_name (EC2 classic security groups) is not supported '
                'in a VPC.  Use security_group_ids instead.')
        if not ((ami is not None) ^
                (valid_ami_owners is not None or
                 valid_ami_location_regex is not None)):
            raise ValueError(
                'You must provide either a specific ami, or one or both of '
                'valid_ami_location_regex and valid_ami_owners')
        self.ami = ami
        if valid_ami_owners is not None:
            if isinstance(valid_ami_owners, integer_types):
                valid_ami_owners = (valid_ami_owners,)
            else:
                for element in valid_ami_owners:
                    if not isinstance(element, integer_types):
                        raise ValueError(
                            'valid_ami_owners should be int or iterable '
                            'of ints', element)
        if valid_ami_location_regex is not None:
            if not isinstance(valid_ami_location_regex, string_types):
                raise ValueError(
                    'valid_ami_location_regex should be a string')
            else:
                # verify that regex will compile
                re.compile(valid_ami_location_regex)
        if spot_instance and price_multiplier is None and max_spot_price is None:
            raise ValueError('You must provide either one, or both, of '
                             'price_multiplier or max_spot_price')
        self.valid_ami_owners = None
        if valid_ami_owners:
            self.valid_ami_owners = [str(o) for o in valid_ami_owners]
        self.valid_ami_location_regex = valid_ami_location_regex
        self.instance_type = instance_type
        self.keypair_name = keypair_name
        self.security_name = security_name
        self.user_data = user_data
        self.spot_instance = spot_instance
        self.max_spot_price = max_spot_price
        self.volumes = volumes
        self.price_multiplier = price_multiplier
        self.product_description = product_description

        if None not in [placement, region]:
            self.placement = '%s%s' % (region, placement)
        else:
            self.placement = None
        if identifier is None:
            assert secret_identifier is None, (
                'supply both or neither of identifier, secret_identifier')
            if aws_id_file_path is None:
                home = os.environ['HOME']
                default_path = os.path.join(home, '.ec2', 'aws_id')
                if os.path.exists(default_path):
                    aws_id_file_path = default_path
            if aws_id_file_path:
                log.msg('WARNING: EC2LatentWorker is using deprecated '
                        'aws_id file')
                with open(aws_id_file_path, 'r') as aws_file:
                    identifier = aws_file.readline().strip()
                    secret_identifier = aws_file.readline().strip()
        else:
            assert aws_id_file_path is None, \
                'if you supply the identifier and secret_identifier, ' \
                'do not specify the aws_id_file_path'
            assert secret_identifier is not None, \
                'supply both or neither of identifier, secret_identifier'

        region_found = None

        # Make the EC2 connection.
        self.session = session
        if self.session is None:
            if region is not None:
                for r in boto3.Session(
                        aws_access_key_id=identifier,
                        aws_secret_access_key=secret_identifier).get_available_regions('ec2'):

                    if r == region:
                        region_found = r

                if region_found is not None:
                    self.session = boto3.Session(
                        region_name=region,
                        aws_access_key_id=identifier,
                        aws_secret_access_key=secret_identifier)
                else:
                    raise ValueError(
                        'The specified region does not exist: ' + region)

            else:
                # boto2 defaulted to us-east-1 when region was unset, we
                # mimic this here in boto3
                region = botocore.session.get_session().get_config_variable('region')
                if region is None:
                    region = 'us-east-1'
                self.session = boto3.Session(
                    aws_access_key_id=identifier,
                    aws_secret_access_key=secret_identifier,
                    region_name=region
                )

        self.ec2 = self.session.resource('ec2')

        # Make a keypair
        #
        # We currently discard the keypair data because we don't need it.
        # If we do need it in the future, we will always recreate the keypairs
        # because there is no way to
        # programmatically retrieve the private key component, unless we
        # generate it and store it on the filesystem, which is an unnecessary
        # usage requirement.
        try:
            self.ec2.KeyPair(self.keypair_name).load()
            # key_pair.delete() # would be used to recreate
        except ClientError as e:
            if 'InvalidKeyPair.NotFound' not in str(e):
                if 'AuthFailure' in str(e):
                    log.msg('POSSIBLE CAUSES OF ERROR:\n'
                            '  Did you supply your AWS credentials?\n'
                            '  Did you sign up for EC2?\n'
                            '  Did you put a credit card number in your AWS '
                            'account?\n'
                            'Please doublecheck before reporting a problem.\n')
                raise
            # make one; we would always do this, and stash the result, if we
            # needed the key (for instance, to SSH to the box).  We'd then
            # use paramiko to use the key to connect.
            self.ec2.create_key_pair(KeyName=keypair_name)

        # create security group
        if security_name:
            try:
                self.ec2.SecurityGroup(security_name).load()
            except ClientError as e:
                if 'InvalidGroup.NotFound' in str(e):
                    self.security_group = self.ec2.create_security_group(
                        GroupName=security_name,
                        Description='Authorization to access the buildbot instance.')
                    # Authorize the master as necessary
                    # TODO this is where we'd open the hole to do the reverse pb
                    # connect to the buildbot
                    # ip = urllib.urlopen(
                    #     'http://checkip.amazonaws.com').read().strip()
                    # self.security_group.authorize('tcp', 22, 22, '%s/32' % ip)
                    # self.security_group.authorize('tcp', 80, 80, '%s/32' % ip)
                else:
                    raise

        # get the image
        if self.ami is not None:
            self.image = self.ec2.Image(self.ami)
        else:
            # verify we have access to at least one acceptable image
            discard = self.get_image()
            assert discard

        # get the specified elastic IP, if any
        if elastic_ip is not None:
            # Using ec2.vpc_addresses.filter(PublicIps=[elastic_ip]) throws a
            # NotImplementedError("Filtering not supported in describe_address.") in moto
            # https://github.com/spulec/moto/blob/100ec4e7c8aa3fde87ff6981e2139768816992e4/moto/ec2/responses/elastic_ip_addresses.py#L52
            addresses = self.ec2.meta.client.describe_addresses(
                PublicIps=[elastic_ip])['Addresses']
            if not addresses:
                raise ValueError(
                    'Could not find EIP for IP: ' + elastic_ip)
            allocation_id = addresses[0]['AllocationId']
            elastic_ip = self.ec2.VpcAddress(allocation_id)
        self.elastic_ip = elastic_ip
        self.subnet_id = subnet_id
        self.security_group_ids = security_group_ids
        self.classic_security_groups = [
            self.security_name] if self.security_name else None
        self.instance_profile_name = instance_profile_name
        self.tags = tags
        self.block_device_map = self.create_block_device_mapping(
            block_device_map) if block_device_map else None

    def create_block_device_mapping(self, mapping_definitions):
        if isinstance(mapping_definitions, list):
            for mapping_definition in mapping_definitions:
                ebs = mapping_definition.get('Ebs')
                if ebs:
                    ebs.setdefault('DeleteOnTermination', True)
            return mapping_definitions

        reportDeprecatedWorkerNameUsage(
            "Use of dict value to 'block_device_map' of EC2LatentWorker "
            "constructor is deprecated. Please use a list matching the AWS API "
            "https://docs.aws.amazon.com/AWSEC2/latest/APIReference/API_BlockDeviceMapping.html"
        )
        return self._convert_deprecated_block_device_mapping(mapping_definitions)

    def _convert_deprecated_block_device_mapping(self, mapping_definitions):
        new_mapping_definitions = []
        for dev_name, dev_config in iteritems(mapping_definitions):
            new_dev_config = {}
            new_dev_config['DeviceName'] = dev_name
            if dev_config:
                new_dev_config['Ebs'] = {}
                new_dev_config['Ebs']['DeleteOnTermination'] = dev_config.get(
                    'delete_on_termination', True)
                new_dev_config['Ebs'][
                    'Encrypted'] = dev_config.get('encrypted')
                new_dev_config['Ebs']['Iops'] = dev_config.get('iops')
                new_dev_config['Ebs'][
                    'SnapshotId'] = dev_config.get('snapshot_id')
                new_dev_config['Ebs']['VolumeSize'] = dev_config.get('size')
                new_dev_config['Ebs'][
                    'VolumeType'] = dev_config.get('volume_type')
                new_dev_config['Ebs'] = self._remove_none_opts(
                    new_dev_config['Ebs'])
            new_mapping_definitions.append(new_dev_config)
        return new_mapping_definitions
        if not mapping_definitions:
            return None

        for mapping_definition in mapping_definitions:
            ebs = mapping_definition.get('Ebs')
            if ebs:
                ebs.setdefault('DeleteOnTermination', True)

        return mapping_definitions

    def get_image(self):
        # pylint: disable=too-many-nested-blocks

        if self.image is not None:
            return self.image
        images = self.ec2.images.all()
        if self.valid_ami_owners:
            images = images.filter(Owners=self.valid_ami_owners)
        if self.valid_ami_location_regex:
            level = 0
            options = []
            get_match = re.compile(self.valid_ami_location_regex).match
            for image in images:
                # Image must be available
                if image.state != 'available':
                    continue
                # Image must match regex
                match = get_match(image.image_location)
                if not match:
                    continue
                # Gather sorting information
                alpha_sort = int_sort = None
                if level < 2:
                    try:
                        alpha_sort = match.group(1)
                    except IndexError:
                        level = 2
                    else:
                        if level == 0:
                            try:
                                int_sort = int(alpha_sort)
                            except ValueError:
                                level = 1
                options.append([int_sort, alpha_sort,
                                image.image_location, image.id, image])
            if level:
                log.msg('sorting images at level %d' % level)
                options = [candidate[level:] for candidate in options]
        else:
            options = [(image.image_location, image.id, image) for image
                       in images]
        options.sort()
        log.msg('sorted images (last is chosen): %s' %
                (', '.join(
                    ['%s (%s)' % (candidate[-1].id, candidate[-1].image_location)
                     for candidate in options])))
        if not options:
            raise ValueError('no available images match constraints')
        return options[-1][-1]

    def dns(self):
        if self.instance is None:
            return None
        return self.instance.public_dns_name
    dns = property(dns)

    def start_instance(self, build):
        if self.instance is not None:
            raise ValueError('instance active')
        if self.spot_instance:
            return threads.deferToThread(self._request_spot_instance)
        return threads.deferToThread(self._start_instance)

    def _remove_none_opts(self, *args, **opts):
        if args:
            opts = args[0]
        return dict((k, v) for k, v in iteritems(opts) if v is not None)

    def _start_instance(self):
        image = self.get_image()
        launch_opts = dict(
            ImageId=image.id, KeyName=self.keypair_name,
            SecurityGroups=self.classic_security_groups,
            InstanceType=self.instance_type, UserData=self.user_data,
            Placement=self.placement, MinCount=1, MaxCount=1,
            SubnetId=self.subnet_id, SecurityGroupIds=self.security_group_ids,
            IamInstanceProfile=self._remove_none_opts(
                Name=self.instance_profile_name,
            ),
            BlockDeviceMappings=self.block_device_map
        )
        launch_opts = self._remove_none_opts(launch_opts)
        reservations = self.ec2.create_instances(
            **launch_opts
        )

        self.instance = reservations[0]
        instance_id, start_time = self._wait_for_instance()
        if None not in [instance_id, image.id, start_time]:
            if self.tags:
                self.instance.create_tags(Tags=[{"Key": k, "Value": v}
                                                for k, v in self.tags.items()])
            return [instance_id, image.id, start_time]
        else:
            self.failed_to_start(self.instance.id, self.instance.state['Name'])

    def stop_instance(self, fast=False):

        if self.instance is None:
            # be gentle.  Something may just be trying to alert us that an
            # instance never attached, and it's because, somehow, we never
            # started.
            return defer.succeed(None)
        instance = self.instance
        self.output = self.instance = None
        return threads.deferToThread(
            self._stop_instance, instance, fast)

    def _attach_volumes(self):
        for volume_id, device_node in self.volumes:
            vol = self.ec2.Volume(volume_id)
            vol.attach_to_instance(
                InstanceId=self.instance.id, Device=device_node)
            log.msg('Attaching EBS volume %s to %s.' %
                    (volume_id, device_node))

    def _stop_instance(self, instance, fast):
        if self.elastic_ip is not None:
            self.elastic_ip.association.delete()
        instance.reload()
        if instance.state['Name'] not in (SHUTTINGDOWN, TERMINATED):
            instance.terminate()
            log.msg('%s %s terminating instance %s' %
                    (self.__class__.__name__, self.workername, instance.id))
        duration = 0
        interval = self._poll_resolution
        if fast:
            goal = (SHUTTINGDOWN, TERMINATED)
            instance.reload()
        else:
            goal = TERMINATED,
        while instance.state['Name'] not in goal:
            time.sleep(interval)
            duration += interval
            if duration % 60 == 0:
                log.msg(
                    '%s %s has waited %d minutes for instance %s to end' %
                    (self.__class__.__name__, self.workername, duration // 60,
                     instance.id))
            instance.reload()
        log.msg('%s %s instance %s %s '
                'after about %d minutes %d seconds' %
                (self.__class__.__name__, self.workername,
                 instance.id, goal, duration // 60, duration % 60))

    def _bid_price_from_spot_price_history(self):
        timestamp_yesterday = time.gmtime(int(time.time() - 86400))
        spot_history_starttime = time.strftime(
            '%Y-%m-%dT%H:%M:%SZ', timestamp_yesterday)
        spot_prices = self.ec2.meta.client.describe_spot_price_history(
            StartTime=spot_history_starttime,
            ProductDescriptions=[self.product_description],
            AvailabilityZone=self.placement)
        price_sum = 0.0
        price_count = 0
        for price in spot_prices['SpotPriceHistory']:
            if price['InstanceType'] == self.instance_type:
                price_sum += float(price['SpotPrice'])
                price_count += 1
        if price_count == 0:
            bid_price = 0.02
        else:
            bid_price = (price_sum / price_count) * self.price_multiplier
        return bid_price

    def _request_spot_instance(self):
        if self.price_multiplier is None:
            bid_price = self.max_spot_price
        else:
            bid_price = self._bid_price_from_spot_price_history()
            if self.max_spot_price is not None \
               and bid_price > self.max_spot_price:
                bid_price = self.max_spot_price
        log.msg('%s %s requesting spot instance with price %0.4f' %
                (self.__class__.__name__, self.workername, bid_price))
        reservations = self.ec2.meta.client.request_spot_instances(
            SpotPrice=str(bid_price),
            LaunchSpecification=self._remove_none_opts(
                ImageId=self.ami,
                KeyName=self.keypair_name,
                SecurityGroups=self.classic_security_groups,
                UserData=self.user_data,
                InstanceType=self.instance_type,
                Placement=self._remove_none_opts(
                    AvailabilityZone=self.placement,
                ),
                SubnetId=self.subnet_id,
                SecurityGroupIds=self.security_group_ids,
                BlockDeviceMappings=self.block_device_map,
                IamInstanceProfile=self._remove_none_opts(
                    Name=self.instance_profile_name,
                )
            )
        )
        request, success = self._wait_for_request(
            reservations['SpotInstanceRequests'][0])
        if not success:
            raise LatentWorkerFailedToSubstantiate()
        instance_id = request['InstanceId']
        self.instance = self.ec2.Instance(instance_id)
        image = self.get_image()
        instance_id, start_time = self._wait_for_instance()
        return instance_id, image.id, start_time

    def _wait_for_instance(self):
        log.msg('%s %s waiting for instance %s to start' %
                (self.__class__.__name__, self.workername, self.instance.id))
        duration = 0
        interval = self._poll_resolution
        while self.instance.state['Name'] == PENDING:
            time.sleep(interval)
            duration += interval
            if duration % 60 == 0:
                log.msg('%s %s has waited %d minutes for instance %s' %
                        (self.__class__.__name__, self.workername, duration // 60,
                         self.instance.id))
            self.instance.reload()

        if self.instance.state['Name'] == RUNNING:
            self.properties.setProperty("instance", self.instance.id, "Worker")
            self.output = self.instance.console_output().get('Output')
            minutes = duration // 60
            seconds = duration % 60
            log.msg('%s %s instance %s started on %s '
                    'in about %d minutes %d seconds (%s)' %
                    (self.__class__.__name__, self.workername,
                     self.instance.id, self.dns, minutes, seconds,
                     self.output))
            if self.elastic_ip is not None:
                self.elastic_ip.associate(InstanceId=self.instance.id)
            start_time = '%02d:%02d:%02d' % (
                minutes // 60, minutes % 60, seconds)
            if self.volumes:
                self._attach_volumes()
            return self.instance.id, start_time
        else:
            self.failed_to_start(self.instance.id, self.instance.state['Name'])

    def _wait_for_request(self, reservation):
        duration = 0
        interval = self._poll_resolution
        requests = self.ec2.meta.client.describe_spot_instance_requests(
            SpotInstanceRequestIds=[reservation['SpotInstanceRequestId']])
        request = requests['SpotInstanceRequests'][0]
        request_status = request['Status']['Code']
        while request_status in SPOT_REQUEST_PENDING_STATES:
            time.sleep(interval)
            duration += interval
            if duration % 60 == 0:
                log.msg('%s %s has waited %d minutes for spot request %s' %
                        (self.__class__.__name__, self.workername, duration // 60,
                         request['SpotInstanceRequestId']))
            requests = self.ec2.meta.client.describe_spot_instance_requests(
                SpotInstanceRequestIds=[reservation['SpotInstanceRequestId']])
            request = requests['SpotInstanceRequests'][0]
            request_status = request['Status']['Code']
        if request_status == FULFILLED:
            minutes = duration // 60
            seconds = duration % 60
            log.msg('%s %s spot request %s fulfilled '
                    'in about %d minutes %d seconds' %
                    (self.__class__.__name__, self.workername,
                     request['SpotInstanceRequestId'], minutes, seconds))
            return request, True
        elif request_status == PRICE_TOO_LOW:
            self.ec2.meta.client.cancel_spot_instance_requests(
                SpotInstanceRequestIds=[request['SpotInstanceRequestId']])
            log.msg('%s %s spot request rejected, spot price too low' %
                    (self.__class__.__name__, self.workername))
            raise LatentWorkerFailedToSubstantiate(
                request['SpotInstanceRequestId'], request.status)
        else:
            log.msg('%s %s failed to fulfill spot request %s with status %s' %
                    (self.__class__.__name__, self.workername,
                     request['SpotInstanceRequestId'], request_status))
            raise LatentWorkerFailedToSubstantiate(
                request['SpotInstanceRequestId'], request.status)
