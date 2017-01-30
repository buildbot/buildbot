=================
Secret Management
=================

Requirements
============
Buildbot steps might need secrets to execute their actions.
Secrets are used to execute commands or to create authenticated network connections.
Secrets could be a ssh key, a password, or a file content like a wgetrc file or a public ssh key.

Secrets and providers
=====================

To implement actions with secrets, secrets have to be readable by Buildbot.
To preserve confidentiality the secrets values should not be printed.
Secrets could not be stored in the Buildbot configuration (master.cfg) if the source code is shared in SCM like git.
Buildbot allows providers to retrieve secrets. Secrets providers are based on a file storage or a secret backend.
In a file system secrets are written in a file. In the backend secrets are stored in a data base.
Secrets providers are instantiated if needed in the master configuration.
The secret manager is a Buildbot service. The secret manager returns the specific provider results related to the providers registered in the configuration.
Using a backend framework, allows to encrypt and store the values.

Kind of secret
--------------

Secret case key:value
`````````````````````

For example a password could be used in a command by Buildbot.
The secret is a couple ``key:value``.
The password is stored with 2 entities: a ``key``, and a ``value``.

Secret case with file content
`````````````````````````````

The file content is stored with a secured content (ssh key, or some text to add in a wgetrc file).
The new file content will be written during a step where secrets are populated.
The content is returned by the provider and the file name is given as an argument when the step is created.
the file name is the ``key`` and the content is stored as ``value``.
An other example could be a key used to send a ssh command, usually stored in a ``ssh text file`` (like id_rsa) in the :envvar:`HOME` directory.
The ssh key registering is done with 2 entities: a ``name`` (ssh file name), a ``value`` (ssh_key value).

Secrets storage
---------------

Storage in a file directory storing secrets
```````````````````````````````````````````

In a directory, a file named ``key`` contains the text ``value``.
e.g: a file ``user`` contains the text ``password``.

Backend Storage: Vault
``````````````````````
Vault secures, stores, and tightly controls access to secrets. Vault presents an unified API to access multiple backends.
To be authenticated in Vault, Buildbot need to send to the vault server a token.
The token is generated when the Vault instance is initialized for the first time.
This token and the Vault server address have to be stored in the master configuration.
Vault store tuples (key, value).

Secrets manager
---------------

The manager is a Buildbot service.
The secret manager allows Buildbot to get secrets calling a get method.
Depending to the kind of storage choosen and declared in the configuration, the manager get the selected provider and return the value.

Secrets providers
-----------------

The secrets providers are sub services manager, implementing the specific getters, related to the storage chosen.

File provider
`````````````

In the master configuration the provider is instantiated through a Buildbot service secret manager with the file directory path.
File secrets provider reads the file named by the key wanted by Buildbot and returns the contained text value.
The provider SecretInFile allows Buildbot read secrets in the secret directory.
In the master configuration, the provider will be added by:

.. code-block:: shell

    c['secretsManagers'] = [util.SecretInFile(directory="/path/toSecretsFiles"]

Vault provider
``````````````

In the master configuration the Vault provider is instantiated trough the Buildbot service manager as a secret provider with the the Vault server address and the Vault token.
The token key is the only ``secrets`` written in the Buildbot configuration.
The provider SecretInVault allows Buildbot to read secrets in Vault.
For more informations about Vault please visit: _`Vault`: https://www.vaultproject.io/
With Vault, secrets are never visible to the normal user via logs and thus are transmitted directly to the workers, using the :class:`Obfuscated`.
The class Obfuscated changes the password characters in ``####`` characters in the logs.
In the master configuration, the provider will be added by:

.. code-block:: shell

    c['secretsManagers'] = [util.SecretInVault(
                            vaultToken="8e77569d-0c39-2219-dfdf-7389a7bfe020",
                            vaultServer="http://localhost:8200"
    )]

How to configure a Vault instance
---------------------------------

A Docker file to install Vault
``````````````````````````````

A Docker file is available to help users installing Vault.

In the Docker file directory:

.. code-block:: shell

    docker-compose up # to launch the install

Starting the vault instance
```````````````````````````

Once the docker image is created, launch a shell terminal on the docker image:

.. code-block:: shell

      docker exec -i -t ``docker_vault_image_name`` /bin/sh

Then, export the environment variable VAULT_ADDR needed to init Vault.

.. code-block:: shell

      export VAULT_ADDR='vault.server.adress'

Init Vault
``````````

Vault has to initialized to launch encryption and allows users to access to the secret backend.
The first initialization will provide keys to seal/unseal Vault in the future and a root token needed by Vault commands.

.. code-block:: shell

    / # vault init
      Unseal Key 1: aaabc93f348fa9629d522e5d57afe51794e21f27d6e76ad661fa479031dca32501
      Unseal Key 2: 551a42ad50b4a7c30b91c072a317447d92da7f3e3df1e6c5b6d433553c91bf2002
      Unseal Key 3: 7b8506686123bd97c8b0da4a7a25996bf73d4ccfb7d168995a7c0277f37ebd0503
      Unseal Key 4: 3f440f6173091ba8f91aeaccf20799a2a5885e593d68f4e5365c60dd66ebf5f304
      Unseal Key 5: 11db4ba4429e01fc3a3bf0f42b3544b4c06f6da8b7487ab9daf451ffa904f7d605
      Initial Root Token: 8e77569d-0c39-2219-dfdf-7389a7bfe020

Export the root token once given:

.. code-block:: shell

      export VAULT_TOKEN=VAULT_TOKEN

Unsealing Vault
```````````````

Vault has to be unsealed manually. Follow the Vault manual for more informations.
Unsealing Vault allows Buildbot to use the feature. 3 unseal keys are needed. Please save the unseal keys in a secure file.

How to use secrets in Buildbot
------------------------------

A Generic API function helps to populate the secrets in a master build step.
Secrets populated are finally stored in files like wgetrc or id_rsa keys file.
Secrets are also interpolated in the build like properties are, and will be used in a command line for example.
Then secrets files are deleted at the end of the build.

The step PopulateSecrets is instantiated with kwargs arguments, the key is the file name, the value is the secret key, that will return the value during the step.

Secrets values are obfuscated in the steps logs.

.. code-block:: python

        # e.g in a build:
        f1.addStep(PopulateSecrets(ssh_keys=['ssh_user'], wgetrc=['userpassword'])
        f1.addStep(ShellCommand(Interpolate("wget -u user -p %{secrets:userpassword}s %{prop:urltofetch}s")))
        f1.addStep(RemoveSecrets(['ssh_keys'])
