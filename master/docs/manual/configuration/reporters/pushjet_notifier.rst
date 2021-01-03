.. bb:reporter:: PushjetNotifier

.. _Pushjet: https://pushjet.io/

PushjetNotifier
+++++++++++++++

.. py:class:: buildbot.reporters.pushover.PushjetNotifier

Pushjet_ is another instant notification service, similar to :bb:reporter:`PushoverNotifier`.
To use this reporter, you need to generate a Pushjet service and provide its secret.

The following parameters are accepted by this class:

``generators``
    (list)
    A list of instances of ``IReportGenerator`` which defines the conditions of when the messages will be sent and contents of them.
    See :ref:`Report-Generators` for more information.

``secret``
    This is a secret token for your Pushjet service. See http://docs.pushjet.io/docs/creating-a-new-service to learn how to create a new Pushjet service and get its secret token.
    Can be a :ref:`Secret`.

``levels``
    Dictionary of Pushjet notification levels. The keys of the dictionary can be ``change``, ``failing``, ``passing``, ``warnings``, ``exception`` and are equivalent to the ``mode`` strings. The values are integers between 0...5, specifying notification priority. In case a mode is missing from this dictionary, the default value set by Pushover is used.

``base_url``
    Base URL for custom Pushjet instances. Defaults to https://api.pushjet.io.
