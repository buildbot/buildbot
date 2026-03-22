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

from __future__ import annotations

import os
import re
import time
from typing import Any

from twisted.internet import defer
from twisted.internet import threads
from twisted.python import log

from buildbot import config
from buildbot.interfaces import LatentWorkerFailedToSubstantiate
from buildbot.worker import AbstractLatentWorker

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

    def __init__(
        self,
        name: str,
        password: str,
        instance_type: str,
        ami: str | None = None,
        valid_ami_owners: int | list[int] | tuple[int, ...] | None = None,
        valid_ami_location_regex: str | None = None,
        elastic_ip: str | None = None,
        identifier: str | None = None,
        secret_identifier: str | None = None,
        aws_id_file_path: str | None = None,
        user_data: str | None = None,
        region: str | None = None,
        keypair_name: str | None = None,
        security_name: str | None = None,
        spot_instance: bool = False,
        max_spot_price: float | None = 1.6,
        volumes: list[Any] | None = None,
        placement: str | None = None,
        price_multiplier: float | None = 1.2,
        tags: dict[str, str] | None = None,
        product_description: str = 'Linux/UNIX',
        subnet_id: str | list[str] | None = None,
        security_group_ids: list[str] | None = None,
        instance_profile_name: str | None = None,
        block_device_map: list[dict[str, Any]] | None = None,
        session: Any = None,
        **kwargs: Any,
    ) -> None:
        if not boto3:
            config.error("The python module 'boto3' is needed to use a EC2LatentWorker")

        if keypair_name is None:
            config.error("EC2LatentWorker: 'keypair_name' parameter must be specified")

        if security_name is None and not subnet_id:
            config.error("EC2LatentWorker: 'security_name' parameter must be specified")

        if volumes is None:
            volumes = []

        if tags is None:
            tags = {}

        super().__init__(name, password, **kwargs)

        if security_name and subnet_id:
            raise ValueError(
                'security_name (EC2 classic security groups) is not supported '
                'in a VPC.  Use security_group_ids instead.'
            )
        if not (
            (ami is not None)
            ^ (valid_ami_owners is not None or valid_ami_location_regex is not None)
        ):
            raise ValueError(
                'You must provide either a specific ami, or one or both of '
                'valid_ami_location_regex and valid_ami_owners'
            )
        self.ami = ami
        if valid_ami_owners is not None:
            if isinstance(valid_ami_owners, int):
                valid_ami_owners = (valid_ami_owners,)
            else:
                for element in valid_ami_owners:
                    if not isinstance(element, int):
                        raise ValueError(
                            'valid_ami_owners should be int or iterable of ints', element
                        )
        if valid_ami_location_regex is not None:
            if not isinstance(valid_ami_location_regex, str):
                raise ValueError('valid_ami_location_regex should be a string')
            # pre-compile the regex
            valid_ami_location_regex = re.compile(valid_ami_location_regex)  # type: ignore[assignment]
        if spot_instance and price_multiplier is None and max_spot_price is None:
            raise ValueError(
                'You must provide either one, or both, of price_multiplier or max_spot_price'
            )
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
            self.placement: str | None = f'{region}{placement}'
        else:
            self.placement = None
        if identifier is None:
            assert secret_identifier is None, (
                'supply both or neither of identifier, secret_identifier'
            )
            if aws_id_file_path is None:
                home = os.environ['HOME']
                default_path = os.path.join(home, '.ec2', 'aws_id')
                if os.path.exists(default_path):
                    aws_id_file_path = default_path
            if aws_id_file_path:
                log.msg('WARNING: EC2LatentWorker is using deprecated aws_id file')
                with open(aws_id_file_path, encoding='utf-8') as aws_file:
                    identifier = aws_file.readline().strip()
                    secret_identifier = aws_file.readline().strip()
        else:
            assert aws_id_file_path is None, (
                'if you supply the identifier and secret_identifier, '
                'do not specify the aws_id_file_path'
            )
            assert secret_identifier is not None, (
                'supply both or neither of identifier, secret_identifier'
            )

        region_found = None

        # Make the EC2 connection.
        self.session = session
        if self.session is None:
            if region is not None:
                for r in boto3.Session(
                    aws_access_key_id=identifier, aws_secret_access_key=secret_identifier
                ).get_available_regions('ec2'):
                    if r == region:
                        region_found = r

                if region_found is not None:
                    self.session = boto3.Session(
                        region_name=region,
                        aws_access_key_id=identifier,
                        aws_secret_access_key=secret_identifier,
                    )
                else:
                    raise ValueError('The specified region does not exist: ' + region)

            else:
                # boto2 defaulted to us-east-1 when region was unset, we
                # mimic this here in boto3
                region = botocore.session.get_session().get_config_variable('region')
                if region is None:
                    region = 'us-east-1'
                self.session = boto3.Session(
                    aws_access_key_id=identifier,
                    aws_secret_access_key=secret_identifier,
                    region_name=region,
                )

        self.ec2 = self.session.resource('ec2')
        self.ec2_client = self.session.client('ec2')

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
                    log.msg(
                        'POSSIBLE CAUSES OF ERROR:\n'
                        '  Did you supply your AWS credentials?\n'
                        '  Did you sign up for EC2?\n'
                        '  Did you put a credit card number in your AWS '
                        'account?\n'
                        'Please doublecheck before reporting a problem.\n'
                    )
                raise
            # make one; we would always do this, and stash the result, if we
            # needed the key (for instance, to SSH to the box).  We'd then
            # use paramiko to use the key to connect.
            self.ec2.create_key_pair(KeyName=keypair_name)

        # create security group
        if security_name:
            try:
                self.ec2_client.describe_security_groups(GroupNames=[security_name])
            except ClientError as e:
                if 'InvalidGroup.NotFound' in str(e):
                    self.security_group = self.ec2.create_security_group(
                        GroupName=security_name,
                        Description='Authorization to access the buildbot instance.',
                    )
                    # Authorize the master as necessary
                    # TODO this is where we'd open the hole to do the reverse pb
                    # connect to the buildbot
                    # ip = urllib.urlopen(
                    #     'http://checkip.amazonaws.com').read().strip()
                    # self.security_group.authorize('tcp', 22, 22, '{}/32'.format(ip))
                    # self.security_group.authorize('tcp', 80, 80, '{}/32'.format(ip))
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
            addresses = self.ec2.meta.client.describe_addresses(PublicIps=[elastic_ip])['Addresses']
            if not addresses:
                raise ValueError('Could not find EIP for IP: ' + elastic_ip)
            allocation_id = addresses[0]['AllocationId']
            elastic_ip = self.ec2.VpcAddress(allocation_id)
        self.elastic_ip = elastic_ip
        self.subnet_id = subnet_id
        self.security_group_ids = security_group_ids
        self.classic_security_groups = [self.security_name] if self.security_name else None
        self.instance_profile_name = instance_profile_name
        self.tags = tags
        self.block_device_map = (
            self.create_block_device_mapping(block_device_map) if block_device_map else None
        )

    def create_block_device_mapping(
        self, mapping_definitions: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        if not isinstance(mapping_definitions, list):
            config.error("EC2LatentWorker: 'block_device_map' must be a list")

        for mapping_definition in mapping_definitions:
            ebs = mapping_definition.get('Ebs')
            if ebs:
                ebs.setdefault('DeleteOnTermination', True)
        return mapping_definitions

    def get_image(self) -> Any:
        # pylint: disable=too-many-nested-blocks

        if self.image is not None:
            return self.image
        images = self.ec2.images.all()
        if self.valid_ami_owners:
            images = images.filter(Owners=self.valid_ami_owners)
        if self.valid_ami_location_regex:
            level = 0
            options = []
            get_match = self.valid_ami_location_regex.match  # type: ignore[attr-defined]
            for image in images:
                # Image must be available
                if image.state != 'available':
                    continue
                # Image must match regex
                if image.image_location is None:
                    continue
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
                options.append([int_sort, alpha_sort, image.image_location, image.id, image])
            if level:
                log.msg(f'sorting images at level {level}')
                options = [candidate[level:] for candidate in options]
        else:
            options = [(image.image_location, image.id, image) for image in images]  # type: ignore[misc]
        options.sort()
        images = [f'{candidate[-1].id} ({candidate[-1].image_location})' for candidate in options]
        log.msg(f"sorted images (last is chosen): {', '.join(images)}")
        if not options:
            raise ValueError('no available images match constraints')
        return options[-1][-1]

    def _dns(self) -> str | None:
        if self.instance is None:
            return None
        return self.instance.public_dns_name

    dns = property(_dns)

    def start_instance(self, build: Any) -> defer.Deferred[Any]:
        if self.instance is not None:
            raise ValueError('instance active')
        if self.spot_instance:
            return threads.deferToThread(self._request_spot_instance)
        return threads.deferToThread(self._start_instance)

    def _remove_none_opts(self, *args: Any, **opts: Any) -> dict[str, Any]:
        if args:
            opts = args[0]
        return dict((k, v) for k, v in opts.items() if v is not None)

    def _start_instance(self) -> list[str] | None:
        image = self.get_image()
        launch_opts = {
            "ImageId": image.id,
            "KeyName": self.keypair_name,
            "SecurityGroups": self.classic_security_groups,
            "InstanceType": self.instance_type,
            "UserData": self.user_data,
            "Placement": self._remove_none_opts(
                AvailabilityZone=self.placement,
            ),
            "MinCount": 1,
            "MaxCount": 1,
            "SubnetId": self.subnet_id,
            "SecurityGroupIds": self.security_group_ids,
            "IamInstanceProfile": self._remove_none_opts(
                Name=self.instance_profile_name,
            ),
            "BlockDeviceMappings": self.block_device_map,
        }
        launch_opts = self._remove_none_opts(launch_opts)
        reservations = self.ec2.create_instances(**launch_opts)

        self.instance = reservations[0]
        instance_id, start_time = self._wait_for_instance()  # type: ignore[misc]
        if None not in [instance_id, image.id, start_time]:
            return [instance_id, image.id, start_time]
        else:
            self.failed_to_start(self.instance.id, self.instance.state['Name'])
        return None

    def stop_instance(self, fast: bool = False) -> defer.Deferred[None]:  # type: ignore[override]
        if self.instance is None:
            # be gentle.  Something may just be trying to alert us that an
            # instance never attached, and it's because, somehow, we never
            # started.
            return defer.succeed(None)
        instance = self.instance
        self.output = self.instance = None
        return threads.deferToThread(self._stop_instance, instance, fast)

    def _attach_volumes(self) -> None:
        for volume_id, device_node in self.volumes:
            vol = self.ec2.Volume(volume_id)
            vol.attach_to_instance(InstanceId=self.instance.id, Device=device_node)  # type: ignore[union-attr]
            log.msg(f'Attaching EBS volume {volume_id} to {device_node}.')

    def _stop_instance(self, instance: Any, fast: bool) -> None:
        if self.elastic_ip is not None:
            self.elastic_ip.association.delete()  # type: ignore[attr-defined]
        instance.reload()
        if instance.state['Name'] not in (SHUTTINGDOWN, TERMINATED):
            instance.terminate()
            log.msg(
                f'{self.__class__.__name__} {self.workername} terminating instance {instance.id}'
            )
        duration = 0
        interval = self._poll_resolution
        if fast:
            goal: tuple[str, ...] = (SHUTTINGDOWN, TERMINATED)
            instance.reload()
        else:
            goal = (TERMINATED,)
        while instance.state['Name'] not in goal:
            time.sleep(interval)
            duration += interval
            if duration % 60 == 0:
                log.msg(
                    f'{self.__class__.__name__} {self.workername} has waited {duration // 60} '
                    f'minutes for instance {instance.id} to end'
                )
            instance.reload()
        log.msg(
            f'{self.__class__.__name__} {self.workername} instance {instance.id} {goal} after '
            f'about {duration // 60} minutes {duration % 60} seconds'
        )

    def _bid_price_from_spot_price_history(self) -> float:
        timestamp_yesterday = time.gmtime(int(time.time() - 86400))
        spot_history_starttime = time.strftime('%Y-%m-%dT%H:%M:%SZ', timestamp_yesterday)
        spot_prices = self.ec2.meta.client.describe_spot_price_history(
            StartTime=spot_history_starttime,
            ProductDescriptions=[self.product_description],
            AvailabilityZone=self.placement,
        )
        price_sum = 0.0
        price_count = 0
        for price in spot_prices['SpotPriceHistory']:
            if price['InstanceType'] == self.instance_type:
                price_sum += float(price['SpotPrice'])
                price_count += 1
        if price_count == 0:
            bid_price = 0.02
        else:
            bid_price = (price_sum / price_count) * self.price_multiplier  # type: ignore[operator]
        return bid_price

    def _request_spot_instance(self) -> tuple[str, str, str]:
        if self.price_multiplier is None:
            bid_price = self.max_spot_price
        else:
            bid_price = self._bid_price_from_spot_price_history()
            if self.max_spot_price is not None and bid_price > self.max_spot_price:
                bid_price = self.max_spot_price
        log.msg(
            f'{self.__class__.__name__} {self.workername} requesting spot instance with '
            f'price {bid_price:0.4f}'
        )

        image = self.get_image()
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
                ),
            ),
        )
        request, success = self._thd_wait_for_request(reservations['SpotInstanceRequests'][0])
        if not success:
            raise LatentWorkerFailedToSubstantiate()
        instance_id = request['InstanceId']
        self.instance = self.ec2.Instance(instance_id)
        instance_id, start_time = self._wait_for_instance()  # type: ignore[misc]
        return instance_id, image.id, start_time

    def _wait_for_instance(self) -> tuple[str, str] | None:
        log.msg(
            f'{self.__class__.__name__} {self.workername} waiting for instance '
            f'{self.instance.id} to start'  # type: ignore[union-attr]
        )
        duration = 0
        interval = self._poll_resolution
        while self.instance.state['Name'] == PENDING:  # type: ignore[union-attr]
            time.sleep(interval)
            duration += interval
            if duration % 60 == 0:
                log.msg(
                    f'{self.__class__.__name__} {self.workername} has waited {duration // 60} '
                    f'minutes for instance {self.instance.id}'  # type: ignore[union-attr]
                )
            self.instance.reload()  # type: ignore[union-attr]

        if self.instance.state['Name'] == RUNNING:  # type: ignore[union-attr]
            self.properties.setProperty("instance", self.instance.id, "Worker")  # type: ignore[union-attr]
            self.output = self.instance.console_output().get('Output')  # type: ignore[union-attr]
            minutes = duration // 60
            seconds = duration % 60
            log.msg(
                f'{self.__class__.__name__} {self.workername} instance {self.instance.id} '  # type: ignore[union-attr]
                f'started on {self.dns} in about {minutes} minutes {seconds} seconds '
                f'({self.output})'
            )
            if self.elastic_ip is not None:
                self.elastic_ip.associate(InstanceId=self.instance.id)  # type: ignore[union-attr,attr-defined]
            start_time = f'{minutes // 60:02d}:{minutes % 60:02d}:{seconds:02d}'
            if self.volumes:
                self._attach_volumes()
            if self.tags:
                self.instance.create_tags(  # type: ignore[union-attr]
                    Tags=[{"Key": k, "Value": v} for k, v in self.tags.items()]
                )
            return self.instance.id, start_time  # type: ignore[union-attr]
        else:
            self.failed_to_start(self.instance.id, self.instance.state['Name'])  # type: ignore[union-attr]
            return None  # This is just to silence warning, above line throws an exception

    def _thd_wait_for_request(self, reservation: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        duration = 0
        interval = self._poll_resolution

        while True:
            # Sometimes it can take a second or so for the spot request to be
            # ready.  If it isn't ready, you will get a "Spot instance request
            # ID 'sir-abcd1234' does not exist" exception.
            try:
                requests = self.ec2.meta.client.describe_spot_instance_requests(
                    SpotInstanceRequestIds=[reservation['SpotInstanceRequestId']]
                )
            except ClientError as e:
                if 'InvalidSpotInstanceRequestID.NotFound' in str(e):
                    requests = None
                else:
                    raise

            if requests is not None:
                request = requests['SpotInstanceRequests'][0]
                request_status = request['Status']['Code']
                if request_status not in SPOT_REQUEST_PENDING_STATES:
                    break

            time.sleep(interval)
            duration += interval
            if duration % 10 == 0:
                log.msg(
                    f"{self.__class__.__name__} {self.workername} has waited {duration} "
                    f"seconds for spot request {reservation['SpotInstanceRequestId']}"
                )

        if request_status == FULFILLED:
            minutes = duration // 60
            seconds = duration % 60
            log.msg(
                f"{self.__class__.__name__} {self.workername} spot request "
                f"{request['SpotInstanceRequestId']} fulfilled in about {minutes} minutes "
                f"{seconds} seconds"
            )
            return request, True
        elif request_status == PRICE_TOO_LOW:
            self.ec2.meta.client.cancel_spot_instance_requests(
                SpotInstanceRequestIds=[request['SpotInstanceRequestId']]
            )
            log.msg(
                f'{self.__class__.__name__} {self.workername} spot request rejected, spot '
                'price too low'
            )
            raise LatentWorkerFailedToSubstantiate(request['SpotInstanceRequestId'], request_status)
        else:
            log.msg(
                f"{self.__class__.__name__} {self.workername} failed to fulfill spot request "
                f"{request['SpotInstanceRequestId']} with status {request_status}"
            )
            # try to cancel, just for good measure
            self.ec2.meta.client.cancel_spot_instance_requests(
                SpotInstanceRequestIds=[request['SpotInstanceRequestId']]
            )
            raise LatentWorkerFailedToSubstantiate(request['SpotInstanceRequestId'], request_status)
