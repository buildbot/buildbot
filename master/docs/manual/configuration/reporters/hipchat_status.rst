.. bb:reporter:: HipchatStatusPush

HipchatStatusPush
+++++++++++++++++

.. py:currentmodule:: buildbot.reporters.hipchat

.. py:class:: HipchatStatusPush

.. code-block:: python

    from buildbot.plugins import reporters

    hs = reporters.HipchatStatusPush('private-token', endpoint='https://chat.yourcompany.com')
    c['services'].append(hs)

:class:`HipchatStatusPush` publishes a custom message using `Hipchat API v2 <https://www.hipchat.com/docs/apiv2>`_.
The message is published to a user and/or room in Hipchat,

It requires `txrequests`_ package to allow interaction with Hipchat API.

It uses API token auth, and the token owner is required to have at least message/notification access to each destination.


.. py:class:: HipchatStatusPush(auth_token, endpoint="https://api.hipchat.com",
                                builder_room_map=None, builder_user_map=None,
                                wantProperties=False, wantSteps=False, wantPreviousBuild=False, wantLogs=False)

    :param string auth_token: Private API token with access to the "Send Message" and "Send Notification" scopes. (can be a :ref:`Secret`)
    :param string endpoint: (optional) URL of your Hipchat server. Defaults to https://api.hipchat.com
    :param dictionary builder_room_map: (optional) If specified, will forward events about a builder (based on name) to the corresponding room ID.
    :param dictionary builder_user_map: (optional) If specified, will forward events about a builder (based on name) to the corresponding user ID.
    :param boolean wantProperties: (optional) include 'properties' in the build dictionary
    :param boolean wantSteps: (optional) include 'steps' in the build dictionary
    :param boolean wantLogs: (optional) include 'logs' in the steps dictionaries.
        This needs wantSteps=True.
        This dumps the *full* content of logs.
    :param boolean wantPreviousBuild: (optional) include 'prev_build' in the build dictionary
    :param boolean verify: disable ssl verification for the case you use temporary self signed certificates
    :param boolean debug: logs every requests and their response


.. note::

   No message will be sent if the message is empty or there is no destination found.

.. note::

   If a builder name appears in both the room and user map, the same message will be sent to both destinations.


Json object spec
~~~~~~~~~~~~~~~~

The default json object contains the minimal required parameters to send a message to Hipchat.

.. code-block:: json

    {
        "message": "Buildbot started/finished build MyBuilderName (with result success) here: http://mybuildbot.com/#/builders/23",
        "id_or_email": "12"
    }


If you require different parameters, the Hipchat reporter utilizes the template design pattern and will call :py:func:`getRecipientList` :py:func:`getMessage` :py:func:`getExtraParams`
before sending a message. This allows you to easily override the default implementation for those methods. All of those methods can be deferred.

Method signatures:

.. py:method:: getRecipientList(self, build, event_name)

     :param build: A :class:`Build` object
     :param string event_name: the name of the event trigger for this invocation. either 'new' or 'finished'
     :returns: Deferred

     The deferred should return a dictionary containing the key(s) 'id_or_email' for a private user message and/or
     'room_id_or_name' for room notifications.

.. py:method:: getMessage(self, build, event_name)

     :param build: A :class:`Build` object
     :param string event_name: the name of the event trigger for this invocation. either 'new' or 'finished'
     :returns: Deferred

     The deferred should return a string to send to Hipchat.

.. py:method:: getExtraParams(self, build, event_name)

     :param build: A :class:`Build` object
     :param string event_name: the name of the event trigger for this invocation. either 'new' or 'finished'
     :returns: Deferred

     The deferred should return a dictionary containing any extra parameters you wish to include in your JSON POST
     request that the Hipchat API can consume.

Here's a complete example:

.. code-block:: python

    class MyHipchatStatusPush(HipChatStatusPush):
        name = "MyHipchatStatusPush"

        # send all messages to the same room
        def getRecipientList(self, build, event_name):
            return {
                'room_id_or_name': 'AllBuildNotifications'
            }

        # only send notifications on finished events
        def getMessage(self, build, event_name):
            event_messages = {
                'finished': 'Build finished.'
            }
            return event_messages.get(event_name, '')

        # color notifications based on the build result
        # and alert room on build failure
        def getExtraParams(self, build, event_name):
            result = {}
            if event_name == 'finished':
                result['color'] = 'green' if build['results'] == 0 else 'red'
                result['notify'] = (build['results'] != 0)
            return result

.. _txrequests: https://pypi.python.org/pypi/txrequests
