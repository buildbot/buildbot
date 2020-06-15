.. bb:step:: P4

.. _Step-P4:

P4
++

.. py:class:: buildbot.steps.source.p4.P4

The :bb:step:`P4` build step creates a `Perforce <http://www.perforce.com/>`_ client specification and performs an update.

.. code-block:: python

    from buildbot.plugins import steps, util

    factory.addStep(steps.P4(
        p4port=p4port,
        p4client=util.WithProperties('%(P4USER)s-%(workername)s-%(buildername)s'),
        p4user=p4user,
        p4base='//depot',
        p4viewspec=p4viewspec,
        mode='incremental'))

You can specify the client spec in two different ways.
You can use the ``p4base``, ``p4branch``, and (optionally) ``p4extra_views`` to build up the viewspec, or you can utilize the ``p4viewspec`` to specify the whole viewspec as a set of tuples.

Using ``p4viewspec`` will allow you to add lines such as:

.. code-block:: none

    //depot/branch/mybranch/...             //<p4client>/...
    -//depot/branch/mybranch/notthisdir/... //<p4client>/notthisdir/...


If you specify ``p4viewspec`` and any of ``p4base``, ``p4branch``, and/or ``p4extra_views`` you will receive a configuration error exception.

``p4base``
    A view into the Perforce depot without branch name or trailing ``/...``.
    Typically ``//depot/proj``.

``p4branch``
    (optional): A single string, which is appended to the p4base as follows ``<p4base>/<p4branch>/...`` to form the first line in the viewspec

``p4extra_views``
    (optional): a list of ``(depotpath, clientpath)`` tuples containing extra views to be mapped into the client specification.
    Both will have ``/...`` appended automatically.
    The client name and source directory will be prepended to the client path.

``p4viewspec``
    This will override any p4branch, p4base, and/or p4extra_views specified.
    The viewspec will be an array of tuples as follows:

    .. code-block:: python

        [('//depot/main/','')]

    It yields a viewspec with just:

    .. code-block:: none

        //depot/main/... //<p4client>/...

``p4viewspec_suffix``
    (optional): The ``p4viewspec`` lets you customize the client spec for a builder but, as the previous example shows, it automatically adds ``...`` at the end of each line.
    If you need to also specify file-level remappings, you can set the ``p4viewspec_suffix`` to ``None`` so that nothing is added to your viewspec:

    .. code-block:: python

        [('//depot/main/...', '...'),
         ('-//depot/main/config.xml', 'config.xml'),
         ('//depot/main/config.vancouver.xml', 'config.xml')]

    It yields a viewspec with:

    .. code-block:: none

        //depot/main/...                  //<p4client>/...
        -//depot/main/config.xml          //<p4client/main/config.xml
        //depot/main/config.vancouver.xml //<p4client>/main/config.xml

    Note how, with ``p4viewspec_suffix`` set to ``None``, you need to manually add ``...`` where you need it.

``p4client_spec_options``
    (optional): By default, clients are created with the ``allwrite rmdir`` options.
    This string lets you change that.

``p4port``
    (optional): the :samp:`{host}:{port}` string describing how to get to the P4 Depot (repository), used as the option `-p` argument for all p4 commands.

``p4user``
    (optional): the Perforce user, used as the option `-u` argument to all p4 commands.

``p4passwd``
    (optional): the Perforce password, used as the option `-p` argument to all p4 commands.

``p4client``
    (optional): The name of the client to use.
    In ``mode='full'`` and ``mode='incremental'``, it's particularly important that a unique name is used for each checkout directory to avoid incorrect synchronization.
    For this reason, Python percent substitution will be performed on this value to replace ``%(prop:workername)s`` with the worker name and ``%(prop:buildername)s`` with the builder name.
    The default is ``buildbot_%(prop:workername)s_%(prop:buildername)s``.

``p4line_end``
    (optional): The type of line ending handling P4 should use.
    This is added directly to the client spec's ``LineEnd`` property.
    The default is ``local``.

``p4extra_args``
    (optional): Extra arguments to be added to the P4 command-line for the ``sync`` command.
    So for instance if you want to sync only to populate a Perforce proxy (without actually syncing files to disk), you can do:

    .. code-block:: python

        P4(p4extra_args=['-Zproxyload'], ...)

``use_tickets``
    Set to ``True`` to use ticket-based authentication, instead of passwords (but you still need to specify ``p4passwd``).

``stream``
    Set to ``True`` to use a stream-associated workspace, in which case ``p4base`` and ``p4branch`` are used to determine the stream path.
