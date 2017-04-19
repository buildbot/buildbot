Credential Management
=====================

Definition
----------

Buildbot needs to send and/or execute commands requiring credentials.

The goal is to store credentials used by Buildbot commands.

Credential could not be stored in ``buildbot.config`` or ``master.config`` because the configuration is available in a source control management.

Credential are stored in the Buildbot database.

Credentials once stored are obfuscated.

Credential case: SSH Key
------------------------

A key used to send a ssh command is usually stored in a ``ssh text file`` (like id_rsa) in the :envvar:`HOME` directory.

The ssh key registering is done with 3 entities: a name (ssh key name), a value (ssh_key value) and a path (where the file is stored).

Credential case: Password
-------------------------

A password could be use in a command by Buildbot.
The password is stored with 2 entities: a ``name``, and a ``value``. No path is inserted.

How to add, delete or modify new credentials
--------------------------------------------

A data API is available to create, delete and modify new credentials.

The data API modifies the 3 entities:
``NAME`` and ``VALUE`` (mandatory), ``PATH`` (not mandatory, as it is not used in the password case).

A data API function helps to register any new credential in the database.

    .. code-block:: bash

        buildbot add-creds http://localhost:8020 --file ~/.ssh/id_rsa --destination '$HOME/.ssh/id_rsa' --name ssh_user
        buildbot add-creds http://localhost:8020  --name userpassword --value mypassword

A data API allows users to modify credential values

    .. code-block:: bash

        buildbot modify-creds http://localhost:8020 --file ~/.ssh/id_rsa --destination '$HOME/.ssh/id_rsa' --name ssh_user
        buildbot modify-creds http://localhost:8020  --name userpassword --value mypassword

A data API allows users to delete credentials

    .. code-block:: bash

        buildbot delete-creds http://localhost:8020 --file ~/.ssh/id_rsa --destination '$HOME/.ssh/id_rsa' --name ssh_user
        buildbot delete-creds http://localhost:8020  --name userpassword --value mypassword

Registering credentials through a Buildbot UI
---------------------------------------------

A Buildbot UI plugin helps to enter, modify and delete the credentials.

Anywhere those credentials are needed, there is a drop down list of the appropriate available credential names, and you just select the appropriate one.

When it's time to change the password, you just change it once or delete it.

Credentials table database description
--------------------------------------

Credentials are stored in the Buildbot database, in a specific table ``credentials``.
The table contains 3 columns  ``NAME``, ``VALUE``, ``PATH``.

e.g:

  +--------------------+-------+----------------+
  | NAME (PRIMARY KEY) | VALUE |     PATH       |
  +--------------------+-------+----------------+
  |   key_user1        | XXXXX | $HOME/buildbot |
  +--------------------+-------+----------------+
  |   pass_user1       | XXXXX |                |
  +--------------------+-------+----------------+

How to use credentials stored in the database
---------------------------------------------

Credentials are stored in the database and have to be use during a build.

A DB API function helps to populate the credentials in a master build step.

Credentials are interpolated in the build like properties are but in a first step, and then deleted at the end of the build.

A class Populate Creds is implemented. Credentials are obfuscated.

    .. code-block:: python

        # e.g in abuild:
        f1.addStep(PopulateCreds(['ssh_user'])
        f1.addStep(ShellCommand(Interpolate("wget -u user -p %{creds:userpassword}s %{prop:urltofetch}s")))
        f1.addStep(RemoveCreds(['ssh_user'])
