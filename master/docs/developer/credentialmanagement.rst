CREDENTIAL MANAGEMENT
=====================

Definition
----------

Buildbot need to send and/or execute commands requiring credentials.

The goal is to store credentials to be use by buildbot and then sent to the worker to be executed.

Those informations will be stored in the Buildbot database.

Credentials ahve to be stored in a database and not in Buildbot configuration because it is
avaliable in source configuration.

Credential case: SSH Key
------------------------

When a ssh command is launched a ssh key will be needed. This key is usualy stored in a
``ssh text file`` in the $HOME directory.

Credential case: Password
-------------------------

A password could be use in a command by Buildbot.
The password will be stored with a name (ID), and a value. No path will be inserted.

Adding new credentails
----------------------

A Buildbot API will be avaliable to enter new credentials. Credentials won't be modified or
deleted by this API to deny read acces to the database.

This API will be avaliable in a new simple Buildbot UI, where the 3 informations will be added.
``NAME`` and ``VALUE`` will be mandatory but the ``PATH`` is not mandatory, as it is not used in
the password case.


API to register credentials
---------------------------

A data api function will help to register any new credential in the database.

.. note:: |
            buildbot add-creds http://localhost:8020 --file ~/.ssh/id_rsa --destination '$HOME/.ssh/id_rsa' --name ssh_user
            buildbot add-creds http://localhost:8020  --name userpassword --value mypassword

A data API will allow users to modify password values

.. note:: |
            buildbot modify-creds http://localhost:8020 --file ~/.ssh/id_rsa --destination '$HOME/.ssh/id_rsa' --name ssh_user
            buildbot modify-creds http://localhost:8020  --name userpassword --value mypassword

A data API will allow users to delete passwords

.. note:: |
            buildbot delete-creds http://localhost:8020 --file ~/.ssh/id_rsa --destination '$HOME/.ssh/id_rsa' --name ssh_user
            buildbot delete-creds http://localhost:8020  --name userpassword --value mypassword

Credential UI
-------------

A UI plugin will help to enter, modify and delete the credentials.

Anywhere those credentials are needed, there is a drop down list of the appropriate available
credentials, and you just select the appropriate one.

When the time comes to change the password, you just change it once or delete it.

Credential table database
--------------------------

Credential will be stored in the Buildbot database, in a specific table ``credentials``.
The table contains 3 columns  ``NAME``, ``VALUE``, ``PATH``.

+------+-------+------+
| NAME | VALUE | PATH |
+------+-------+------+

DB Credentials function
-----------------------

A DB API function will help to populate the credentials in a master build step. credentials will be
avaliable during all the build and removed at the the end.

Using credentials
-----------------

Credentials will be interpolated in the build like properties are but in a first step, and then
deleted at the end of the build.

A class Populate Creds will be implemented. Creds will be obfuscated.

.. note:: |
            e.g in abuild:
            f1.addStep(PopulateCreds(['ssh_user'])
            f1.addStep(ShellCommand(Interpolate("wget -u user -p %{creds:userpassword}s %{prop:urltofetch}s")))
            f1.addStep(RemoveCreds(['ssh_user'])

