# Installing Katana front-end

Katanas front-end is built with a number of node modules and a set of grunt tasks, in order to modify the front-end you'll need to install node.js (http://nodejs.org/).
Once node.js is installed you can following the below commands to install the specific node modules that are used.

```
cd buildbot/www
npm install
```

# Building the Production files

Once you are happy with changes you have made on the front-end you'll need to produce and commit the production files for use on the server, that can be done by doing the following

```
cd buildbot/www
grunt prod
```