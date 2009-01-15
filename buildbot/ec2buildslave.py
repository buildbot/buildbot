import cStringIO
import os
import time
import urllib

import boto
import boto.exception
import paramiko
import twisted.internet.threads
from twisted.python import log

from buildbot.buildslave import AbstractLatentBuildSlave

class EC2LatentBuildSlave(AbstractLatentBuildSlave):

    instance = None
    old_instance = None

    def __init__(self, name, password, instance_type, machine_id,
                 identifier=None, secret_identifier=None,
                 keypair_name='buildbot', security_name='buildbot',
                 max_builds=None, notify_on_missing=[], missing_timeout=60*20,
                 build_wait_timeout=60*10, properties={}):
        AbstractLatentBuildSlave.__init__(
            self, name, password, max_builds, notify_on_missing,
            missing_timeout, build_wait_timeout, properties)
        self.machine_id = machine_id
        self.instance_type = instance_type
        self.keypair_name = keypair_name
        self.security_name = security_name
        if identifier is None:
            assert secret_identifier is None, (
                'supply both or neither of identifier, secret_identifier')
            home = os.environ['HOME']
            aws_id = os.path.join(home, '.ec2', 'aws_id')
            if not os.path.exists(aws_id):
                raise ValueError(
                    "Please supply your AWS access key identifier and secret "
                    "access key identifier either when instantiating this %s "
                    "or in the %s file (on two lines).\n" %
                    (self.__class__.__name__, aws_id))
            aws_file = open(aws_id, 'r')
            try:
                identifier = aws_file.readline().strip()
                secret_identifier = aws_file.readline().strip()
            finally:
                aws_file.close()
        else:
            assert secret_identifier is not None, (
                'supply both or neither of identifier, secret_identifier')
        # Make the EC2 connection.
        self.conn = boto.connect_ec2(identifier, secret_identifier)

        # Delete previously used keypair, if it exists.
        #
        # We always recreate the keypairs because there is no way to
        # programmatically retrieve the private key component, unless we
        # generate it and store it on the filesystem, which is an unnecessary
        # usage requirement.
        try:
            key_pair = self.conn.get_all_key_pairs(keypair_name)[0]
            key_pair.delete()
        except boto.exception.EC2ResponseError, e:
            if e.code != 'InvalidKeyPair.NotFound':
                if e.code == 'AuthFailure':
                    print ('POSSIBLE CAUSES OF ERROR:\n'
                           '  Did you sign up for EC2?\n'
                           '  Did you put a credit card number in your AWS '
                           'account?\n'
                           'Please doublecheck before reporting a problem.\n')
                raise
        # make a new one
        self.key_pair = self.conn.create_key_pair(keypair_name)
        self.private_key = paramiko.RSAKey.from_private_key(
            cStringIO.StringIO(self.key_pair.material.encode('ascii')))

        # create security group
        try:
            group = self.conn.get_all_security_groups(security_name)[0]
        except boto.exception.EC2ResponseError, e:
            if e.code == 'InvalidGroup.NotFound':
                self.security_group = self.conn.create_security_group(
                    security_name,
                    'Authorization to access the buildbot instance.')
                # Authorize the master as necessary
                # XXX this is where we'd open the hole to do the reverse pb
                # connect to the buildbot
                # ip = urllib.urlopen(
                #     'http://checkip.amazonaws.com').read().strip()
                # self.security_group.authorize('tcp', 22, 22, '%s/32' % ip)
                # self.security_group.authorize('tcp', 80, 80, '%s/32' % ip)
            else:
                raise

        # get the image
        self.image = self.conn.get_image(self.machine_id)

    @property
    def dns(self):
        if self.instance is None:
            return None
        return self.instance.public_dns_name

    def start_instance(self):
        if self.instance is not None:
            raise ValueError('instance active')
        return twisted.internet.threads.deferToThread(self._start_instance)

    def _start_instance(self):
        reservation = self.image.run(
            key_name=self.keypair_name, security_groups=[self.security_name],
            instance_type=self.instance_type)
        self.instance = reservation.instances[0]
        log.msg('%s %s starting instance %s' %
                (self.__class__.__name__, self.slavename, self.instance.id))
        duration = 0
        interval = 5
        while self.instance.state == 'pending':
            time.sleep(interval)
            duration += interval
            if duration % 60 == 0:
                log.msg('%s %s has waited %d minutes for instance %s' %
                        (self.__class__.__name__, self.slavename, duration//60,
                         self.instance.id))
            self.instance.update()
        if self.instance.state == 'running':
            self.output = self.instance.get_console_output()
            log.msg('%s %s instance %s started on %s '
                    'in about %d minutes %d seconds (%s)' %
                    (self.__class__.__name__, self.slavename,
                     self.instance.id, self.dns, duration//60, duration%60,
                     self.output.output))
            return True
        else:
            log.msg('%s %s failed to start instance %s (%s)' %
                    (self.__class__.__name__, self.slavename,
                     self.instance.id, self.instance.state))
            return False

    def stop_instance(self):
        if self.instance is None:
            raise ValueError('no instance')
        return twisted.internet.threads.deferToThread(self._stop_instance)

    def _stop_instance(self):
        instance = self.old_instance = self.instance
        self.instance = self.output = None
        instance.update()
        if instance.state not in ('shutting-down', 'terminated'):
            instance.stop()
            log.msg('%s %s terminating instance %s' %
                    (self.__class__.__name__, self.slavename, instance.id))
        duration = 0
        interval = 5
        while instance.state != 'terminated':
            time.sleep(interval)
            duration += interval
            if duration % 60 == 0:
                log.msg(
                    '%s %s has waited %d minutes for instance %s to terminate' %
                    (self.__class__.__name__, self.slavename, duration//60,
                     instance.id))
            instance.update()
        log.msg('%s %s instance %s terminated '
                'in about %d minutes %d seconds' %
                (self.__class__.__name__, self.slavename,
                 instance.id, duration//60, duration%60))
        return True
