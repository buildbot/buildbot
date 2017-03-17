Secrets
-------

.. code-block:: python

  class SecretDetails(object):
      """
      ...
      """

      def __init__(self, source, key, value):

A ``secretDetails`` is a python object initialized with a provider name, a key and a value.
Each parameter is an object property.

.. code-block:: python

  secretdetail = SecretDetails("SourceProvider", "myKey", "myValue")
  print(secretdetail.source)
  "SourceProvider"
  print(secretdetail.key)
  "myKey"
  print(secretdetail.value)
  "myValue"

Secrets founded are stored in a ``secretDetails``.

Secrets manager
---------------

The manager is a Buildbot service manager.

.. code-block:: python

    secretsService = self.master.namedServices['secrets']
    secretDetailsList = secretsService.get(self.secrets)

The service execute a get method.
Depending on the kind of storage chosen and declared in the configuration, the manager get the selected provider and return a list of ``secretDetails``.

Secrets providers
-----------------

The secrets providers are implementing the specific getters, related to the storage chosen.

File provider
`````````````

.. code-block:: python

    c['secretsProviders'] = [util.SecretInFile(directory="/path/toSecretsFiles"]

In the master configuration the provider is instantiated through a Buildbot service secret manager with the file directory path.
File secrets provider reads the file named by the key wanted by Buildbot and returns the contained text value.
The provider SecretInFile allows Buildbot read secrets in the secret directory.

Vault provider
``````````````

.. code-block:: python

    c['secretsProviders'] = [util.SecretInVault(vaultToken=open('VAULT_TOKEN').read(),
                                                vaultServer="http://localhost:8200"
                                                )]

In the master configuration the provider is instantiated through a Buildbot service secret manager with the Vault token and the Vault server address.
Vault secrets provider access to Vault asking the key wanted by Buildbot and returns the contained text value.
The provider SecretInVAult allows Buildbot read secrets in Vault.

Secret Obfuscation
``````````````````

Secrets are never visible to the normal user via logs and thus are transmitted directly to the workers, using the :class:`Obfuscated`.
The class Obfuscated changes the password characters in ``####`` characters in the logs.
