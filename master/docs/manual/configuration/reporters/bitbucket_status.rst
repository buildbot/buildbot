.. bb:reporter:: BitbucketStatusPush

BitbucketStatusPush
+++++++++++++++++++

.. py:currentmodule:: buildbot.reporters.bitbucket

.. code-block:: python

    from buildbot.plugins import reporters
    bs = reporters.BitbucketStatusPush('oauth_key', 'oauth_secret')
    c['services'].append(bs)

:class:`BitbucketStatusPush` publishes build status using `Bitbucket Build Status API <https://confluence.atlassian.com/bitbucket/buildstatus-resource-779295267.html>`_.
The build status is published to a specific commit SHA in Bitbucket.
It tracks the last build for each builderName for each commit built.

It requires `txrequests`_ package to allow interaction with the Bitbucket REST and OAuth APIs.

It uses OAuth 2.x to authenticate with Bitbucket.
To enable this, you need to go to your Bitbucket Settings -> OAuth page.
Click "Add consumer".
Give the new consumer a name, eg 'buildbot', and put in any URL as the callback (this is needed for Oauth 2.x but is not used by this reporter, eg 'http://localhost:8010/callback').
Give the consumer Repositories:Write access.
After creating the consumer, you will then be able to see the OAuth key and secret.

.. py:class:: BitbucketStatusPush(oauth_key, oauth_secret, base_url='https://api.bitbucket.org/2.0/repositories', oauth_url='https://bitbucket.org/site/oauth2/access_token', builders=None)

    :param string oauth_key: The OAuth consumer key. (can be a :ref:`Secret`)
    :param string oauth_secret: The OAuth consumer secret. (can be a :ref:`Secret`)
    :param string base_url: Bitbucket's Build Status API URL
    :param string oauth_url: Bitbucket's OAuth API URL
    :param list builders: only send update for specified builders
    :param boolean verify: disable ssl verification for the case you use temporary self signed certificates
    :param boolean debug: logs every requests and their response

.. _txrequests: https://pypi.python.org/pypi/txrequests
