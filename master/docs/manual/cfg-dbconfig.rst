.. bb:cfg:: dbconfig


DbConfig
--------

DbConfig is an utility for master.cfg to get easy to use key/value storage in the buildbot database

DbConfig can get and store any jsonable object to the db for use by other masters or separate ui plugins to edit them.

The design is voluntary simplistic, the focus is on the easy use rather than efficiency.
A separate db connection is created each time get() or set() is called.

Example:

.. code-block:: python

    from buildbot.plugins import util, worker
    c = BuildmasterConfig = {}
    c['db_url'] = 'mysql://user@pass:mysqlserver/buildbot'
    dbConfig = util.DbConfig(BuildmasterConfig, basedir)
    workers = dbConfig.get("workers")
    c['workers'] = [
        worker.Worker(worker['name'], worker['passwd'],
                      properties=worker.get('properties')),
        for worker in workers
    ]


.. py:class:: DbConfig

    .. py:method:: __init__(BuildmasterConfig, basedir)

        :param BuildmasterConfig: the BuildmasterConfig, where db_url is already configured
        :param basedir: basedir global variable of the master.cfg run environment. Sqlite urls are relative to this dir.

    .. py:method:: get(name, default=MarkerClass)

        :param name: the name of the config variable to retrieve
        :param default: In case the config variable has not been set yet, default is returned if defined, else KeyError is raised.

    .. py:method:: set(name, value)

        :param name: the name of the config variable to be set
        :param value: the value of the config variable to be set
