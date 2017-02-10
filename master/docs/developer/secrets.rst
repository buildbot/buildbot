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
- name of provider where secret has been retrieved,
- key identifier
- value returned by the provider API

Each parameter value could be returned by a function (source(), value(), key()).
``Secrets`` returned by the secrets manager are stored in a ``SecretDetails`` object.

Secrets manager
```````````````
The secret manager is a Buildbot service, providing a get method API to retrieve a secret value.

.. code-block:: python

    secretsService = self.master.namedServices['secrets']
    secretDetails = secretsService.get(secret)

The get API take the secret key as parameters and read the configuration to obtains the list of configured providers.
The manager calls the get method of the configured provider and returns a ``SecretDetails`` if the call succeed.

.. code-block:: python

  c['secretsProviders'] = [SecretsProviderOne(params), SecretsProviderTwo(params)]

If more than one provider is defined in the configuration, the manager returns the first value found.
