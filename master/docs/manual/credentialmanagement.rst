CREDENTIAL MANAGEMENT
=====================

Definition
----------

Buildbot need to send and/or execute commands requiring credentials.

The goal is to store credentials to be use by buildbot and then sent to the worker to be executed.

Those informations are stored in the Buildbot database.

Credentials have to be stored in a database and not in Buildbot configuration because it is
avaliable in source configuration.

Credential case: SSH Key
------------------------

When a ssh command is launched a ssh key is needed. This key is usually stored in a
``ssh text file`` (like id_rsa) in the $HOME directory. The ssh password entry is done with
a name, a value and a path where the file is stored.

Credential case: Password
-------------------------

A password could be use in a command by Buildbot.
The password is stored with a ``name``, and a ``value``. No path is inserted.

Adding new credentials
----------------------

A data API is avaliable to create, delete and modify new credentials.

During creation the data API modifies the 3 informations:
``NAME`` and ``VALUE`` (mandatory), ``PATH`` (not mandatory, as it is not used in
the password case).

A data api function helps to register any new credential in the database.

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

Credentials UI
--------------

An UI plugin helps to enter, modify and delete the credentials.

Anywhere those credentials are needed, there is a drop down list of the appropriate available
credentials, and you just select the appropriate one.

When the time comes to change the password, you just change it once or delete it.

Credentials table database
--------------------------

Credentials is stored in the Buildbot database, in a specific table ``credentials``.
The table contains 3 columns  ``NAME``, ``VALUE``, ``PATH``.

+------+-------+------+
| NAME | VALUE | PATH |
+------+-------+------+

DB Credentials function
-----------------------

A DB API function helps to populate the credentials in a master build step. credentials is
avaliable during all the build and removed at the the end.

Using credentials
-----------------

Credentials are interpolated in the build like properties are but in a first step, and then
deleted at the end of the build.

A class Populate Creds is implemented. Credentials are obfuscated.

    .. code-block:: python

        # e.g in abuild:
        f1.addStep(PopulateCreds(['ssh_user'])
        f1.addStep(ShellCommand(Interpolate("wget -u user -p %{creds:userpassword}s %{prop:urltofetch}s")))
        f1.addStep(RemoveCreds(['ssh_user'])
