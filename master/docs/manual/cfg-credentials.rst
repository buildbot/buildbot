Credential Management
=====================

Definition
----------

Buildbot needs to send and/or execute commands requiring credentials.
The goal is to store credentials used by Buildbot commands.
Buildbot provides a common framework for steps to use credentials.
The framewework provides a way to configure the credentials outside of the master.cfg.
As the master.cfg is usually stored in a SCM like git, those credentials would be available to anybody.
For this reason, the credentials are stored in a Vault instance. Vault have to be installed to use this feauture.
For more informations about Vault, please visit: _`Vault`: https://www.vaultproject.io/
Credentials are never visible to the normal user via logs, and thus are transmitted to the workers using the :class:`Obfuscated`

Several use cases are addressed by this framework:

Credential case: SSH Key
------------------------

A key used to send a ssh command is usually stored in a ``ssh text file`` (like id_rsa) in the :envvar:`HOME` directory.
The ssh key registering is done with 3 entities: a ``name`` (ssh key name), a ``value`` (ssh_key value).

Credential case: Password
-------------------------

A password could be use in a command by Buildbot.
The password is stored with 2 entities: a ``name``, and a ``value``.

Vault to store credentials
--------------------------

Vault secures, stores, and tightly controls access to credentials. Vault presents an unified API to access multiple backends.
Builbot instance need a key and a token to be authentificated by a Vault server.
Vault store tuples (key, value).
An interface between Vault and Buildbot helps to acces to the credentials versus API commands.

How to add, delete or modify new credentials
--------------------------------------------

A data API is available to create, delete and modify new credentials.
The data API modifies the 2 entities: ``name`` and ``value`` (mandatory)
A data API function helps to register and/or modify any new credential in the database.

.. code-block:: bash

    buildbot set-creds http://localhost:8020  --name ssh_user  --value rsa_key
    buildbot set-creds http://localhost:8020  --name userpassword --value mypassword

A data API allows users to delete credentials

.. code-block:: bash

    buildbot delete-creds http://localhost:8020  --name ssh_user
    buildbot delete-creds http://localhost:8020  --name userpassword

Registering credentials through a Buildbot UI
---------------------------------------------

A Buildbot UI plugin helps to enter, modify and delete the credentials.
Anywhere those credentials are needed, there is a drop down list of the appropriate available credential names, and you just select the appropriate one.
When it's time to change the password, you just change it once or delete it.


How to use credentials stored in Vault
--------------------------------------

A Generic API function helps to populate the credentials in a master build step, getting the credentials in Vault backend.
Credentials are interpolated in the build like properties are but in a first step, and then deleted at the end of the build.
The class PopulateCreds take two kwargs arguments, ssh_keys and passwords.
When ssh_keys argument is not empty, a file ``id_rsa_credential_name`` is created for each ssh key needed in the :envvar:`HOME` directory.
Credentials values are obfuscated in the steps logs.

.. code-block:: python

        # e.g in abuild:
        f1.addStep(PopulateCreds(ssh_keys=['ssh_user'], passwords=['userpassword'])
        f1.addStep(ShellCommand(Interpolate("wget -u user -p %{creds:userpassword}s %{prop:urltofetch}s")))
        f1.addStep(RemoveCreds(['ssh_user'])
