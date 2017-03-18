
.. _secretManagement:

=================
Secret Management
=================

Requirements
============

Buildbot steps might need secrets to execute their actions.
Secrets are used to execute commands or to create authenticated network connections.
Secrets may be a SSH key, a password, or a file content like a wgetrc file or a public SSH key.
To preserve confidentiality, the secrets values must not be printed or logged in the twisted or steps logs.
Secrets must not be stored in the Buildbot configuration (master.cfg), as the source code is usually shared in SCM like git.

How to use Buildbot Secret Management
=====================================

Secrets and providers
---------------------

Buildbot implements several providers for secrets retrieval:

- File system based: secrets are written in a file.
  This is a simple solution for example when secrets are managed by config management system like Ansible Vault.

- Third party backend based: secrets are stored by a specialized software.
  These solution are usually more secured.

Secrets providers are configured if needed in the master configuration.
Multiple providers can be configured at once.
The secret manager is a Buildbot service.
The secret manager returns the specific provider results related to the providers registered in the configuration.

How to use secrets in Buildbot
------------------------------

The following example shows a basic usage of secrets in Buildbot.

.. code-block:: python

    # First we declare that the secrets are stored in a directory of the filesystem
    # each file contain one secret identified by the filename
    c['secretsProviders'] = [util.SecretInFile(directory="/path/toSecretsFiles"]

    # then in a buildfactory:

    # use a secret on a shell command via Interpolate
    f1.addStep(ShellCommand(Interpolate("wget -u user -p %{secrets:userpassword}s %{prop:urltofetch}s")))

Secrets are also interpolated in the build like properties are, and will be used in a command line for example.

Secrets storages
----------------

SecretInFile
````````````

.. code-block:: python

    c['secretsProviders'] = [util.SecretInFile(directory="/path/toSecretsFiles"]

In the passed directory, every file contains a secret identified by the filename.

e.g: a file ``user`` contains the text ``pa$$w0rd``.

SecretInVault
`````````````

.. code-block:: python

    c['secretsProviders'] = [util.SecretInVault(
                            vaultToken=open('VAULT_TOKEN').read(),
                            vaultServer="http://localhost:8200"
    )]

Vault secures, stores, and tightly controls access to secrets.
Vault presents a unified API to access multiple backends.
To be authenticated in Vault, Buildbot need to send a token to the vault server.
The token is generated when the Vault instance is initialized for the first time.


In the master configuration, the Vault provider is instantiated through the Buildbot service manager as a secret provider with the the Vault server address and the Vault token.
The provider SecretInVault allows Buildbot to read secrets in Vault.
For more informations about Vault please visit: _`Vault`: https://www.vaultproject.io/

How to configure a Vault instance
---------------------------------

Vault being a very generic system, it can be complex to install for the first time.
Here is a simple tutorial to install the minimal Vault for use with Buildbot.

Use Docker to install Vault
```````````````````````````

A Docker image is available to help users installing Vault.
Without any arguments, the command launches a Docker Vault developer instance, easy to use and test the functions.
The developer version is already initialized and unsealed.
To launch a Vault server please refer to the VaultDocker_ documentation:

.. _vaultDocker: https://hub.docker.com/_/vault/

In a shell:

.. code-block:: shell

    docker run vault

Starting the vault instance
```````````````````````````

Once the Docker image is created, launch a shell terminal on the Docker image:

.. code-block:: shell

      docker exec -i -t ``docker_vault_image_name`` /bin/sh

Then, export the environment variable VAULT_ADDR needed to init Vault.

.. code-block:: shell

      export VAULT_ADDR='vault.server.adress'

Writing secrets
```````````````

By default Vault is initialized with a mount named secret.
To add a new secret:

.. code-block:: shell

      vault write secret/new_secret_key value=new_secret_value
