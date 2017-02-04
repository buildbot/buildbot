
.. _secretManagement:

=================
Secret Management
=================

Requirements
============

Buildbot steps might need secrets to execute their actions.
Secrets are used to execute commands or to create authenticated network connections.
Secrets may be a ssh key, a password, or a file content like a wgetrc file or a public ssh key.
To preserve confidentiality the secrets values must not be logged in the twisted logs or steps logs.
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
The secret manager is a Buildbot service. The secret manager returns the specific provider results related to the providers registered in the configuration.

How to use secrets in Buildbot
------------------------------

The following example shows a basic usage of secrets in buildbot

.. code-block:: python

    # First we declare that the secrets are stored in a directory of the filesystem
    # each file contain one secret identified by the filename
    c['secretsManagers'] = [util.SecretInFile(directory="/path/toSecretsFiles"]

    # then in a buildfactory:

    f1.addStep(PopulateSecrets([
      #  populate a secret by putting the whole data in the file
      dict(secret_worker_path="~/.ssh/id_rsa", secret_keys="ssh_user1"),

      #  populate a secret by putting the secrets inside a template
      dict(secret_worker_path="~/.netrc", template="""
      machine ftp.mycompany.com
        login buildbot
        password {ftppassword}
        machine www.mycompany.com
          login buildbot
          password {webpassword}
      """, secret_keys=["ftppassword", "webpassword"])])

    #  use a secret on a shell command via Interpolate
    f1.addStep(ShellCommand(Interpolate("wget -u user -p %{secrets:userpassword}s %{prop:urltofetch}s")))

    # Remove secrets remove all the secrets that was populated before
    f1.addStep(RemoveSecrets())

Secrets populated are finally stored in files like netrc or id_rsa keys file.
Secrets are also interpolated in the build like properties are, and will be used in a command line for example.
Then secrets files are deleted at the end of the build.

Secrets storages
----------------

SecretInFile
````````````

.. code-block:: python

    c['secretsManagers'] = [util.SecretInFile(directory="/path/toSecretsFiles"]

In the passed directory, every file contains a secret identified by the filename.

e.g: a file ``user`` contains the text ``pa$$w0rd``.

SecretInVault
`````````````

.. code-block:: python

    c['secretsManagers'] = [util.SecretInVault(
                            vaultToken=open('VAULT_TOKEN').read(),
                            vaultServer="http://localhost:8200"
    )]

Vault secures, stores, and tightly controls access to secrets. Vault presents an unified API to access multiple backends.
To be authenticated in Vault, Buildbot need to send a token to the vault server.
The token is generated when the Vault instance is initialized for the first time.


In the master configuration the Vault provider is instantiated trough the Buildbot service manager as a secret provider with the the Vault server address and the Vault token.
The provider SecretInVault allows Buildbot to read secrets in Vault.
For more informations about Vault please visit: _`Vault`: https://www.vaultproject.io/

How to configure a Vault instance
---------------------------------

Vault being a very generic system, it can be complex to install for the first time.
Here is a simple tutorial to install the minimal Vault for use with Buildbot.

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
