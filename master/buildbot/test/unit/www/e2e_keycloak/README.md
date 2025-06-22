This directory contains configuration for a self-hosted KeyCloak instance that can be
used to run e2e test in test_oauth.py.

You will need to create a configuration file, here and below referred to by as
`oauth.conf`. Write the following into it:

```
{
  "KeyCloakAuth": {
    "INSTANCEURI": "http://localhost:8089",
    "REALM": "master",
    "CLIENTID": "buildbot_id",
    "CLIENTSECRET": "<fill in from steps below>"
}
```

It requires manual steps for setup:

 - Run `./generate_key.sh` to generale a keypair that is later used for SSL

 - Run `sudo docker-compose up -d`

 - Go to `https://localhost:8089`, login with username `admin`, password `admin`

 - Go to Clients, click Create client

 - Fill in the following:

    - Client type: OpenID Connect

    - Client ID: buildbot_id

    - Client authentication: On

    - Authorization: On

    - Authentication flow: Standard flow

    - Root URL: `http://localhost:5000`

    - Home URL: `http://localhost:5000`

    - Valid redirect URIs: `http://localhost:5000/*`

    - Valid post logout redirect URIs: `http://localhost:5000/*`

    - Web origins: `+`

 - Go to the newly created client, its Credentials section

 - Note "Client Secret", write it into `oauth.conf` file.

 - Go to Client scopes section of the created client

 - Click `buildbot_id-dedicated`, click "Add predefined mapper"

 - Select `email`, `groups`, `full name`

 - Click Add


