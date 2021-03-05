..
    This is a partially generated document. You can modify it in incremental manner using following command:
    pip install watchdog # install watchmedo
    make html  # to do once
    watchmedo shell-command -p '*.rst' -c 'time sphinx-build -b html -d _build/doctrees  -q . _build/html developer/rest.rst' -wR  # will re-run each time you modify rst file

.. _REST_API:

REST API
========

The REST API is a public interface which can be used by external code to control Buildbot.
Internally, the REST API a thin wrapper around the data API's "Getter" and "Control" sections.
It is also designed, in keeping with REST principles, to be discoverable.
As such, the details of the paths and resources are not documented here.
Begin at the root URL, and see the :ref:`Data_API` documentation for more information.

The precise specifications in RAML format are described in :ref:`REST_API_specs` documentation.

.. contents:: :local:

Versions
~~~~~~~~

The API described here is version 2.
The ad-hoc API from Buildbot-0.8.x, version 1, is no longer supported [#apiv1]_.


The policy for incrementing the version is when there is incompatible change added.
Removing a field or endpoint is considered incompatible change.
Adding a field or endpoint is not considered incompatible, and thus will only be described as a change in release note.
The policy is that we will avoid as much as possible incrementing version.

.. [#apiv1] The JSON API defined by ``status_json.py`` in Buildbot-0.8.x is considered version 1, although its root path was ``json``, not ``api/v1``.

Getting
~~~~~~~

To get data, issue a GET request to the appropriate path.
For example, with a base URL of ``http://build.example.org/buildbot``, the list of masters for builder 9 is available at ``http://build.example.org/buildbot/api/v2/builder/9/master``.

.. bb:rtype:: collection

Collections
~~~~~~~~~~~

Results are formatted in keeping with the `JSON API <http://jsonapi.org/>`_ specification.
The top level of every response is an object.
Its keys are the plural names of the resource types, and the values are lists of objects, even for a single-resource request.
For example:

.. code-block:: json

    {
      "meta": {
        "total": 2
      },
      "schedulers": [
        {
          "master": null,
          "name": "smoketest",
          "schedulerid": 1
        },
        {
          "master": {
            "active": true,
            "last_active": 1369604067,
            "link": "http://build.example.org/api/v2/master/1",
            "masterid": 1,
            "name": "master3:/BB/master"
          },
          "name": "goaheadtryme",
          "schedulerid": 2
        }
      ]
    }

A response may optionally contain extra, related resources beyond those requested.
The ``meta`` key contains metadata about the response, including the total count of resources in a collection.

Several query parameters may be used to affect the results of a request.
These parameters are applied in the order described (so, it is not possible to sort on a field that is not selected, for example).

Field Selection
...............

If only certain fields of each resource are required, the ``field`` query parameter can be used to select them.
For example, the following will select just the names and id's of all schedulers:

* ``http://build.example.org/api/v2/scheduler?field=name&field=schedulerid``

Field selection can be used for either detail (single-entity) or collection (multi-entity) requests.
The remaining options only apply to collection requests.

Filtering
.........

Collection responses may be filtered on any simple top-level field.

To select records with a specific value use the query parameter ``{field}={value}``.
For example, ``http://build.example.org/api/v2/scheduler?name=smoketest`` selects the scheduler named "smoketest".

Filters can use any of the operators listed below, with query parameters of the form ``{field}__{operator}={value}``.

``eq``
    equality, or with the same parameter appearing multiple times, equality with one of the given values (so `foo__eq=x&foo__eq=y` would match resources where foo is `x` or `y`)
``ne``
    inequality, or set exclusion
``lt``
    select resources where the field's value is less than ``{value}``
``le``
    select resources where the field's value is less than or equal to ``{value}``
``gt``
    select resources where the field's value is greater than ``{value}``
``ge``
    select resources where the field's value is greater than or equal to ``{value}``
``contains``
    Select resources where the field's value contains ``{value}``.
    If the parameter is provided multiple times, results containing at least one of the values are returned (so `foo__contains=x&foo__contains=y` would match resources where foo contains `x`, `y` or both).

For example:

* ``http://build.example.org/api/v2/builder?name__lt=cccc``
* ``http://build.example.org/api/v2/buildsets?complete__eq=false``

Boolean values can be given as ``on``/``off``, ``true``/``false``, ``yes``/``no``, or ``1``/``0``.

Sorting
.......

Collection responses may be ordered with the ``order`` query parameter.
This parameter takes a field name to sort on, optionally prefixed with ``-`` to reverse the sort.
The parameter can appear multiple times, and will be sorted lexically with the fields arranged in the given order.
For example:

* ``http://build.example.org/api/v2/buildrequests?order=builderid&order=buildrequestid``

Pagination
..........

Collection responses may be paginated with the ``offset`` and ``limit`` query parameters.
The offset is the 0-based index of the first result to included, after filtering and sorting.
The limit is the maximum number of results to return.
Some resource types may impose a maximum on the limit parameter; be sure to check the resulting links to determine whether further data is available.
For example:

* ``http://build.example.org/api/v2/buildrequests?order=builderid&limit=10``
* ``http://build.example.org/api/v2/buildrequests?order=builderid&offset=20&limit=10``

Controlling
~~~~~~~~~~~

Data API control operations are handled by POST requests using a simplified form of `JSONRPC 2.0 <http://www.jsonrpc.org/specification>`_.
The JSONRPC "method" is mapped to the data API "action", and the parameters are passed to that application.

The following parts of the protocol are not supported:

* positional parameters
* batch requests

Requests are sent as an HTTP POST, containing the request JSON in the body.
The content-type header must be ``application/json``.

A simple example:

.. code-block:: none

    POST http://build.example.org/api/v2/scheduler/4
    --> {"jsonrpc": "2.0", "method": "force",
         "params": {"revision": "abcd", "branch": "dev"},
         "id": 843}
    <-- {"jsonrpc": "2.0", "result": {"buildsetid": 44}, "id": 843}

Authentication
~~~~~~~~~~~~~~

Authentication to the REST API is performed in the same manner as authentication to the main web interface.
Once credentials have been established, a cookie will be set, which must be sent to the buildbot REST API with every request thereafter.

.. code-block:: python

    import requests
    s = requests.Session()
    s.get("https://<buildbot_url>/auth/login", auth=('user', 'passwd'))
    builders = s.get("https://<buildbot_url>/api/v2/builders").json()

For those buildbot instances using OAuth2 authentication providers, it is at the moment not possible to access the authenticated API .
