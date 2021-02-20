.. index:: HTTP Requests
.. bb:step:: HTTPStep
.. bb:step:: POST
.. bb:step:: GET
.. bb:step:: PUT
.. bb:step:: DELETE
.. bb:step:: HEAD
.. bb:step:: OPTIONS
.. _Step-HTTPStep:

HTTP Requests
+++++++++++++

Using the :bb:step:`HTTPStep` step, it is possible to perform HTTP requests in order to trigger another REST service about the progress of the build.

.. note::

   This step requires the `txrequests <https://pypi.python.org/pypi/txrequests>`_ and `requests <https://requests.readthedocs.io/en/master>`_ Python libraries.

The parameters are the following:

``url``
    (mandatory) The URL where to send the request

``method``
    The HTTP method to use (out of ``POST``, ``GET``, ``PUT``, ``DELETE``, ``HEAD`` or ``OPTIONS``), default to ``POST``.

``params``
    Dictionary of URL parameters to append to the URL.

``data``
    The body to attach the request.
    If a dictionary is provided, form-encoding will take place.

``headers``
    Dictionary of headers to send.

``hide_request_headers``
   Iterable of request headers to be hidden from the log.
   The header will be listed in the log but the value will be shown as ``<HIDDEN>``.

``hide_response_headers``
   Iterable of response headers to be hidden from the log.
   The header will be listed in the log but the value will be shown as ``<HIDDEN>``.

``other params``
    Any other keywords supported by the ``requests``
    `api <https://2.python-requests.org/en/master/api/#main-interface>`_
    can be passed to this step.

    .. note::

        The entire Buildbot master process shares a single Requests ``Session`` object.
        This has the advantage of supporting connection re-use and other HTTP/1.1 features.
        However, it also means that any cookies or other state changed by one step will be visible to other steps, causing unexpected results.
        This behavior may change in future versions.

When the method is known in advance, class with the name of the method can also be used.
In this case, it is not necessary to specify the method.

Example:

.. code-block:: python

    from buildbot.plugins import steps, util

    f.addStep(steps.POST('http://myRESTService.example.com/builds',
                         data = {
                            'builder': util.Property('buildername'),
                            'buildnumber': util.Property('buildnumber'),
                            'workername': util.Property('workername'),
                            'revision': util.Property('got_revision')
                         }))
