# Buildbot data module

Buildbot data module is an AngularJS module for Buildbot nine clients.

## Installation

```
$ bower install buildbot-data
```

## Adding dependency to your project

```
angular.module('myModule', ['bbData']);

```

## Building
```
$ yarn install
$ gulp
```
## Running tests
```
$ yarn install
$ karma start
```

## How to test within buildbot/www/base ?

* run `gulp prod` in base (dependencies are installed)
* run `gulp prod` in data_module
* create symlink from `www/data_module/dist` to `www/base/libs/buildbot-data/dist`
* run `gulp dev proxy` in base
* run `gulp dev` in data_module

## How to publish the results (for buildbot maintainers) ?
```
$ vi guanlecoja/config.coffee   # bump the version manually
$ gulp publish
```
This will commit and publish a new tag in the bower repository, with the content of your working directory
