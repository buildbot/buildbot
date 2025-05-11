.. _buildbot_wsgi_dashboards:

Writing Dashboards with Flask_ or Bottle_
-----------------------------------------

Buildbot UI is written in Javascript.
This allows it to be reactive and real time, but comes at a price of a fair complexity.

There is a Buildbot plugin which allows to write a server side generated dashboard, and integrate it in the UI.

.. code-block:: python

    pip install buildbot_wsgi_dashboards flask

This plugin can use any WSGI compatible web framework, Flask_ is a very common one, Bottle_ is
another popular option.

The application needs to implement a ``/index.html`` route, which will render the html code representing the dashboard.

The application framework runs in a thread outside of Twisted. No need to worry about Twisted and asynchronous code.
You can use python-requests_ or any library from the python ecosystem to access other servers.

You could use HTTP in order to access Buildbot :ref:`REST_API`, but you can also use the
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

        ``buildbot_api.dataGet`` is accessible via the WSGI application object passed to
        ``wsgi_dashboards`` plugin (as per the example).

That html code output of the server runs inside React application.

  - It will use the CSS of the React application (including the Bootstrap_ CSS base).
    You can use custom style-sheet with a standard ``style`` tag within your html.
    Custom CSS will be shared with the whole Buildbot application once your dashboard is loaded.
    So you should make sure your custom CSS rules only apply to your dashboard (e.g. by having a
    specific class for your dashboard's main div)

  - It has full access to the application JS context.

The WSGI plugin can be registered as follows:

.. code-block:: python

    dashboardapp = Flask('test', root_path=os.path.dirname(__file__))
    # this allows to work on the template without having to restart Buildbot
    dashboardapp.config['TEMPLATES_AUTO_RELOAD'] = True

    @dashboardapp.route("/index.html")
    def main():
        # This code fetches build data from the data api, and give it to the
        builders = dashboardapp.buildbot_api.dataGet("/builders")
        builds = dashboardapp.buildbot_api.dataGet("/builds", limit=20)

        # properties are actually not used in the template example, but this is
        # how you get more properties
        for build in builds:
            build['properties'] = dashboardapp.buildbot_api.dataGet(
                ("builds", build['buildid'], "properties")
            )

        graph_data = [
            {'x': 1, 'y': 100},
            {'x': 2, 'y': 200},
            {'x': 3, 'y': 300},
            {'x': 4, 'y': 0},
            {'x': 5, 'y': 100},
        ]

        # dashboard.html is a template inside the template directory
        return render_template('dashboard.html', builders=builders, builds=builds,
                               graph_data=graph_data)


    c['www']['plugins']['wsgi_dashboards'] = [
        {
            'name': 'dashboard',
            'caption': 'Test Dashboard',  # Text shown in the menu
            'app': dashboardapp,
            # Priority of the menu item in the menu (lower is higher in the menu)
            'order': 5,
            # An icon from https://react-icons.github.io/react-icons/icons/fa/
            'icon': 'FaChartArea'
        }
    ]

.. _Flask: http://flask.pocoo.org/
.. _Bottle: https://bottlepy.org/docs/dev/
.. _Bootstrap: http://getbootstrap.com/css/
.. _Jinja: http://jinja.pocoo.org/
.. _python-requests: https://requests.readthedocs.io/en/master/
