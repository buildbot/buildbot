.. _secrets:

Secrets
-------

SecretDetails
`````````````

A secret is identified by a couple (key, value).

.. code-block:: python

  class SecretDetails(object):

      def __init__(self, provider, key, value, props=None):

A ``secretDetails`` is a python object initialized with the following parameters:
- provider name to retrieve secrets,
- key identifier
- value returned by the provider API
- properties if needed.

Each parameter is an object property that should returned the value.
``Secrets`` returned by the secrets manager are stored in a ``SecretDetails`` object.

Secrets manager
```````````````
The secret manager is a Buildbot service, providing a get method API to retrieve a secret value.

.. code-block:: python

    secretsService = self.master.namedServices['secrets']
    secretDetails = secretsService.get(secret)

The get API take the secret key as parameters and read the configuration to obtains the list of configured providers.
The manager get the selected provider and returns a ``SecretDetails``.

.. code-block:: python

  c['secretsProviders'] = [SecretsProviderOne(params), SecretsProviderTwo(params)]

If more than one provider is defined in the configuration, the manager returns the first founded value.
