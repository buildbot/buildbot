.. _Manhole:

.. py:module:: buildbot.plugins.util

Manhole
-------

Manhole is an interactive Python shell that gives full access to the Buildbot master instance.
It is probably only useful for Buildbot developers.

Using Manhole requires the ``cryptography`` and ``pyasn1`` python packages to be installed.
These are not part of the normal Buildbot dependencies.

There are several implementations of Manhole available, which differ by the authentication mechanisms and the security of the connection.

.. note::
    Manhole exposes full access to the buildmaster's account (including the ability to modify and delete files).
    It's recommended not to expose the manhole to the Internet and to use a strong password.

.. py:class:: AuthorizedKeysManhole(port, keyfile, ssh_hostkey_dir)

    A manhole implementation that accepts encrypted ssh connections and authenticates by ssh keys.
    The prospective client must have an ssh private key that matches one of the public keys in manhole's authorized keys file.

    :type port: string or int
    :param port: The port to listen on.
        This is a `strports <https://twistedmatrix.com/documents/current/api/twisted.internet.endpoints.html#serverFromString>`__ specification string, like ``tcp:12345`` or ``tcp:12345:interface=127.0.0.1``.
        Bare integers are treated as a simple tcp port.
    :type keyfile: string
    :param keyfile: The path to the file containing public parts of the authorized SSH keys.
        The path is interpreted relative to the buildmaster's basedir.
        The file should contain one public SSH key per line.
        This is the exact same format as used by sshd in ``~/.ssh/authorized_keys``.
    :type ssh_hostkey_dir: string
    :param ssh_hostkey_dir: The path to the directory which contains ssh host keys for this server.

.. py:class:: PasswordManhole(port, username, password, ssh_hostkey_dir)

    A manhole implementation that accepts encrypted ssh connections and authenticates by username and password.

    :type port: string or int
    :param port: The port to listen on.
        This is a `strports <https://twistedmatrix.com/documents/current/api/twisted.internet.endpoints.html#serverFromString>`__ specification string, like ``tcp:12345`` or ``tcp:12345:interface=127.0.0.1``.
        Bare integers are treated as a simple tcp port.
    :type username: string
    :param username: The username to authenticate.
    :type password: string
    :param password: The password of the user to authenticate.
    :type ssh_hostkey_dir: string
    :param ssh_hostkey_dir: The path to the directory which contains ssh host keys for this server.

.. py:class:: TelnetManhole(port, username, password)

    A manhole implementation that accepts unencrypted telnet connections and authenticates by username and password.

    .. note::
        This connection method is not secure and should not be used anywhere where the port is exposed to the Internet.

    :type port: string or int
    :param port: The port to listen on.
        This is a `strports <https://twistedmatrix.com/documents/current/api/twisted.internet.endpoints.html#serverFromString>`__ specification string, like ``tcp:12345`` or ``tcp:12345:interface=127.0.0.1``.
        Bare integers are treated as a simple tcp port.
    :type username: string
    :param username: The username to authenticate.
    :type password: string
    :param password: The password of the user to authenticate.

Using manhole
~~~~~~~~~~~~~

The interactive Python shell can be entered by simply connecting to the host in question.
For instance, in the case of ssh password-based manhole, the configuration may look like this:

.. code-block:: python

  from buildbot import manhole
  c['manhole'] = manhole.PasswordManhole("tcp:1234:interface=127.0.0.1",
                                         "admin", "passwd",
                                         ssh_hostkey_dir="data/ssh_host_keys")

The above `ssh_hostkey_dir` declares a path relative to the buildmaster's basedir to look for ssh keys. To create an ssh key, navigate to the buildmaster's basedir and run:

.. code-block:: bash

  mkdir -p data/ssh_host_keys
  ckeygen3 -t rsa -f "data/ssh_host_keys/ssh_host_rsa_key"

Restart Buildbot and then try to connect to the running buildmaster like this:

.. code-block:: bash

  ssh -p1234 admin@127.0.0.1
  # enter passwd at prompt

After connection has been established, objects can be explored in more depth using `dir(x)` or the helper function `show(x)`.
For example:

.. code-block:: python

  >>> master.workers.workers
  {'example-worker': <Worker 'example-worker', current builders: runtests>}

  >>> show(master)
  data attributes of <buildbot.master.BuildMaster instance at 0x7f7a4ab7df38>
                         basedir : '/home/dustin/code/buildbot/t/buildbot/'...
                       botmaster : <type 'instance'>
                  buildCacheSize : None
                    buildHorizon : None
                     buildbotURL : http://localhost:8010/
                 changeCacheSize : None
                      change_svc : <type 'instance'>
                  configFileName : master.cfg
                              db : <class 'buildbot.db.connector.DBConnector'>
                          db_url : sqlite:///state.sqlite
                                ...
  >>> show(master.botmaster.builders['win32'])
  data attributes of <Builder ''builder'' at 48963528>


The buildmaster's SSH server will use a different host key than the normal sshd running on a typical unix host.
This will cause the ssh client to complain about a `host key mismatch`, because it does not realize there are two separate servers running on the same host.
To avoid this, use a clause like the following in your :file:`.ssh/config` file:

.. code-block:: none

    Host remotehost-buildbot
    HostName remotehost
    HostKeyAlias remotehost-buildbot
    Port 1234
    # use 'user' if you use PasswordManhole and your name is not 'admin'.
    # if you use AuthorizedKeysManhole, this probably doesn't matter.
    User admin
