.. _buildbot_wsgi_dashboards:

Writing Dashboards with Flask_ or Bottle_
-----------------------------------------

Buildbot Nine UI is written in Javascript.
This allows it to be reactive and real time, but comes at a price of a fair complexity.

There is a Buildbot plugin which allows to write a server side generated dashboard, and integrate it in the UI.

.. code-block:: python

    # This needs buildbot and buildbot_www >= 0.9.5
    pip install buildbot_wsgi_dashboards flask

- This plugin can use any WSGI compatible web framework, Flask_ is a very common one, Bottle_ is
  another popular option.

- The application needs to implement a ``/index.html`` route, which will render the html code representing the dashboard.

- The application framework runs in a thread outside of Twisted.
  No need to worry about Twisted and asynchronous code.
  You can use python-requests_ or any library from the python ecosystem to access other servers.

- You could use HTTP in order to access Buildbot :ref:`REST_API`, but you can also use the
  :ref:`Data_API`, via the provided synchronous wrapper.

    .. py:method:: buildbot_api.dataGet(path, filters=None, fields=None, order=None, limit=None, offset=None)

        :param tuple path: A tuple of path elements representing the API path to fetch.
            Numbers can be passed as strings or integers.
        :param filters: result spec filters
        :param fields: result spec fields
        :param order: result spec order
        :param limit: result spec limit
        :param offset: result spec offset
        :raises: :py:exc:`~buildbot.data.exceptions.InvalidPathError`
        :returns: a resource or list, or None

        This is a blocking wrapper to master.data.get as described in :ref:`Data_API`. The
        available paths are described in the :ref:`REST_API`, as well as the nature of return
        values depending on the kind of data that is fetched. Path can be either the REST path e.g.
        ``"builders/2/builds/4"`` or tuple e.g. ``("builders", 2, "builds", 4)``. The latter form
        being more convenient if some path parts are coming from variables. The :ref:`Data_API` and
        :ref:`REST_API` are functionally equivalent except:

        - :ref:`Data_API` does not have HTTP connection overhead.
        - :ref:`Data_API` does not enforce authorization rules.

        ``buildbot_api.dataGet`` is accessible via the WSGI application object passed to
        ``wsgi_dashboards`` plugin (as per the example).

- That html code output of the server runs inside AngularJS application.

  - It will use the CSS of the AngularJS application (including the Bootstrap_ CSS base).
    You can use custom style-sheet with a standard ``style`` tag within your html.
    Custom CSS will be shared with the whole Buildbot application once your dashboard is loaded.
    So you should make sure your custom CSS rules only apply to your dashboard (e.g. by having a
    specific class for your dashboard's main div)

  - It can use some of the AngularJS directives defined by Buildbot UI (currently only buildsummary is usable).
  - It has full access to the application JS context.


.. _Flask: http://flask.pocoo.org/
.. _Bottle: https://bottlepy.org/docs/dev/
.. _Bootstrap: http://getbootstrap.com/css/
.. _Jinja: http://jinja.pocoo.org/
.. _python-requests: https://requests.readthedocs.io/en/master/
