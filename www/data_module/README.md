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
$ npm install
$ gulp
```
## Running tests
```
$ npm install
$ karma start
```

## How to test within buildbot/www/base ?

```
$ cp dist/* ../base/libs/buildbot-data/dist/
```
Then rebuild buildbot base

## How to publish the results (for buildbot maintainers) ?
```
$ vi guanlecoja/config.coffee   # bump the version manually
$ gulp publish
```
This will commit and publish a new tag in the bower repository, with the content of your working directory
