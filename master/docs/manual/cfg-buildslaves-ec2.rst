.. -*- rst -*-

.. index::
   AWS EC2
   BuildSlaves; AWS EC2

Amazon Web Services Elastic Compute Cloud ("AWS EC2")
=====================================================

`EC2 <http://aws.amazon.com/ec2/>`_ is a web service that allows you to start virtual machines in an Amazon data center.
Please see their website for details, including costs.
Using the AWS EC2 latent buildslaves involves getting an EC2 account with AWS and setting up payment; customizing one or more EC2 machine images ("AMIs") on your desired operating system(s) and publishing them (privately if needed); and configuring the buildbot master to know how to start your customized images for "substantiating" your latent slaves.

This document will guide you through setup of a AWS EC2 latent buildslave:

.. contents::
   :depth: 1
   :local:

Get an AWS EC2 Account
----------------------

To start off, to use the AWS EC2 latent buildslave, you need to get an AWS developer account and sign up for EC2.
Although Amazon often changes this process, these instructions should help you get started:

1. Go to http://aws.amazon.com/ and click to "Sign Up Now" for an AWS account.

2. Once you are logged into your account, you need to sign up for EC2.
   Instructions for how to do this have changed over time because Amazon changes their website, so the best advice is to hunt for it.
   After signing up for EC2, it may say it wants you to upload an x.509 cert.
   You will need this to create images (see below) but it is not technically necessary for the buildbot master configuration.

3. You must enter a valid credit card before you will be able to use EC2.
   Do that under 'Payment Method'.

4. Make sure you're signed up for EC2 by going to :menuselection:`Your Account --> Account Activity` and verifying EC2 is listed.

Create an AMI
-------------

Now you need to create an AMI and configure the master.
You may need to run through this cycle a few times to get it working, but these instructions should get you started.

Creating an AMI is out of the scope of this document.
The `EC2 Getting Started Guide <http://docs.amazonwebservices.com/AWSEC2/latest/GettingStartedGuide/>`_ is a good resource for this task.
Here are a few additional hints.

* When an instance of the image starts, it needs to automatically start a buildbot slave that connects to your master (to create a buildbot slave, :ref:`Creating-a-buildslave`; to make a daemon, :ref:`Launching-the-daemons`).
* You may want to make an instance of the buildbot slave, configure it as a standard buildslave in the master (i.e., not as a latent slave), and test and debug it that way before you turn it into an AMI and convert to a latent slave in the master.

Configure the Master with an EC2LatentBuildSlave
------------------------------------------------

Now let's assume you have an AMI that should work with the EC2LatentBuildSlave.
It's now time to set up your buildbot master configuration.

You will need some information from your AWS account: the `Access Key Id` and the `Secret Access Key`.
If you've built the AMI yourself, you probably already are familiar with these values.
If you have not, and someone has given you access to an AMI, these hints may help you find the necessary values:

* While logged into your AWS account, find the "Access Identifiers" link (either on the left, or via :menuselection:`Your Account --> Access Identifiers`.
* On the page, you'll see alphanumeric values for "Your Access Key Id:" and "Your Secret Access Key:".
  Make a note of these.
  Later on, we'll call the first one your ``identifier`` and the second one your ``secret_identifier``\.

When creating an EC2LatentBuildSlave in the buildbot master configuration, the first three arguments are required.
The name and password are the first two arguments, and work the same as with normal buildslaves.
The next argument specifies the type of the EC2 virtual machine (available options as of this writing include ``m1.small``, ``m1.large``, ``m1.xlarge``, ``c1.medium``, and ``c1.xlarge``; see the EC2 documentation for descriptions of these machines).

Here is the simplest example of configuring an EC2 latent buildslave.
It specifies all necessary remaining values explicitly in the instantiation.

::

    from buildbot.plugins import buildslave
    c['slaves'] = [
        buildlsave.EC2LatentBuildSlave('bot1', 'sekrit', 'm1.large',
                                       ami='ami-12345',
                                       identifier='publickey',
                                       secret_identifier='privatekey'
                                       )
    ]

The ``ami`` argument specifies the AMI that the master should start.
The ``identifier`` argument specifies the AWS `Access Key Id`, and the ``secret_identifier`` specifies the AWS `Secret Access Key`\.
Both the AMI and the account information can be specified in alternate ways.

.. note::

   Whoever has your ``identifier`` and ``secret_identifier`` values can request AWS work charged to your account, so these values need to be carefully protected.
   Another way to specify these access keys is to put them in a separate file.
   Buildbot supports the standard AWS credentials file.
   You can then make the access privileges stricter for this separate file, and potentially let more people read your main configuration file.
   If your master is running in EC2, you can also use IAM roles for EC2 to delegate permissions.

You can make an :file:`.aws` directory in the home folder of the user running the buildbot master.
In that directory, create a file called :file:`credentials`.
The format of the file should be as follows, replacing ``identifier`` and ``secret_identifier`` with the credentials obtained before.

::

    [default]
    aws_access_key_id = identifier
    aws_secret_access_key = secret_identifier

If you are using IAM roles, no config file is required.
Then you can instantiate the build slave as follows.

::

    from buildbot.plugins import buildslave
    c['slaves'] = [
        buildslave.EC2LatentBuildSlave('bot1', 'sekrit', 'm1.large',
                                       ami='ami-12345')
    ]

Previous examples used a particular AMI.
If the Buildbot master will be deployed in a process-controlled environment, it may be convenient to specify the AMI more flexibly.
Rather than specifying an individual AMI, specify one or two AMI filters.

In all cases, the AMI that sorts last by its location (the S3 bucket and manifest name) will be preferred.

One available filter is to specify the acceptable AMI owners, by AWS account number (the 12 digit number, usually rendered in AWS with hyphens like "1234-5678-9012", should be entered as in integer).

::

    from buildbot.plugins import buildslave
    bot1 = buildslave.EC2LatentBuildSlave('bot1', 'sekrit', 'm1.large',
                                          valid_ami_owners=[11111111111,
                                                            22222222222],
                                          identifier='publickey',
                                          secret_identifier='privatekey')

The other available filter is to provide a regular expression string that will be matched against each AMI's location (the S3 bucket and manifest name).

::

    from buildbot.plugins import buildslave
    bot1 = buildslave.EC2LatentBuildSlave(
            'bot1', 'sekrit', 'm1.large',
            valid_ami_location_regex=r'buildbot\-.*/image.manifest.xml',
            identifier='publickey', secret_identifier='privatekey')

The regular expression can specify a group, which will be preferred for the sorting.
Only the first group is used; subsequent groups are ignored.

::

    from buildbot.plugins import buildslave
    bot1 = buildslave.EC2LatentBuildSlave(
        'bot1', 'sekrit', 'm1.large',
        valid_ami_location_regex=r'buildbot\-.*\-(.*)/image.manifest.xml',
        identifier='publickey', secret_identifier='privatekey')

If the group can be cast to an integer, it will be.
This allows 10 to sort after 1, for instance.

::

    from buildbot.plugins import buildslave
    bot1 = buildslave.EC2LatentBuildSlave(
            'bot1', 'sekrit', 'm1.large',
            valid_ami_location_regex=r'buildbot\-.*\-(\d+)/image.manifest.xml',
            identifier='publickey', secret_identifier='privatekey')

In addition to using the password as a handshake between the master and the slave, you may want to use a firewall to assert that only machines from a specific IP can connect as slaves.
This is possible with AWS EC2 by using the Elastic IP feature.
To configure, generate a Elastic IP in AWS, and then specify it in your configuration using the ``elastic_ip`` argument.

::

    from buildbot.plugins import buildslave
    c['slaves'] = [
        buildslave.EC2LatentBuildSlave('bot1', 'sekrit', 'm1.large',
                                       'ami-12345',
                                       identifier='publickey',
                                       secret_identifier='privatekey',
                                       elastic_ip='208.77.188.166')
    ]

One other way to configure a slave is by settings AWS tags.
They can for example be used to have a more restrictive security `IAM <http://aws.amazon.com/iam/>`_ policy.
To get Buildbot to tag the latent slave specify the tag keys and values in your configuration using the ``tags`` argument.

::

    from buildbot.plugins import buildslave
    c['slaves'] = [
        buildslave.EC2LatentBuildSlave('bot1', 'sekrit', 'm1.large',
                                       'ami-12345',
                                       identifier='publickey',
                                       secret_identifier='privatekey',
                                       tags={'SomeTag': 'foo'})
    ]

The :class:`EC2LatentBuildSlave` supports all other configuration from the standard :class:`BuildSlave`.
The ``missing_timeout`` and ``notify_on_missing`` specify how long to wait for an EC2 instance to attach before considering the attempt to have failed, and email addresses to alert, respectively.
``missing_timeout`` defaults to 20 minutes.

``volumes`` expects a list of (volume_id, mount_point) tuples to attempt attaching when your instance has been created.

``keypair_name`` and ``security_name`` allow you to specify different names for these AWS EC2 values.
They both default to ``latent_buildbot_slave``.

Spot instances
--------------

If you would prefer to use spot instances for running your builds, you can accomplish that by passing in a True value to the ``spot_instance`` parameter to the EC2LatentBuildSlave constructor.
Additionally, you may want to specify ``max_spot_price`` and ``price_multiplier`` in order to limit your builds' budget consumption.

::

    from buildbot.plugins import buildslave
    c['slaves'] = [
        buildslave.EC2LatentBuildSlave('bot1', 'sekrit', 'm1.large',
                                       'ami-12345', region='us-west-2',
                                       identifier='publickey',
                                       secret_identifier='privatekey',
                                       elastic_ip='208.77.188.166',
                                       placement='b', spot_instance=True,
                                       max_spot_price=0.09,
                                       price_multiplier=1.15,
                                       product_description='Linux/UNIX')
    ]

This example would attempt to create a m1.large spot instance in the us-west-2b region costing no more than $0.09/hour.
The spot prices for 'Linux/UNIX' spot instances in that region over the last 24 hours will be averaged and multiplied by the ``price_multiplier`` parameter, then a spot request will be sent to Amazon with the above details.

When a spot request fails
-------------------------

In some cases Amazon may reject a spot request because the spot price, determined by taking the 24-hour average of that availability zone's spot prices for the given product description, is lower than the current price.
The optional parameters ``retry`` and ``retry_price_adjustment`` allow for resubmitting the spot request with an adjusted price.
If the spot request continues to fail, and the number of attempts exceeds the value of the ``retry`` parameter, an error message will be logged.

::

    from buildbot.plugins import buildslave
    c['slaves'] = [
        buildslave.EC2LatentBuildSlave('bot1', 'sekrit', 'm1.large',
                                       'ami-12345', region='us-west-2',
                                       identifier='publickey',
                                       secret_identifier='privatekey',
                                       elastic_ip='208.77.188.166',
                                       placement='b', spot_instance=True,
                                       max_spot_price=0.09,
                                       price_multiplier=1.15,
                                       retry=3,
                                       retry_price_adjustment=1.1)
    ]

In this example, a spot request will be sent with a bid price of 15% above the 24-hour average.
If the request fails with the status **price-too-low**, the request will be resubmitted up to twice, each time with a 10% increase in the bid price.
If the request succeeds, the buildslave will substantiate as normal and run any pending builds.
