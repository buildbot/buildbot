.. _WWW-data-module:

Javascript Data Module
======================

Data_module is a reusable angularJS module used to access buildbot's data api from the browser.
Its main purpose is to handle the 3 way binding.


2 way binding is the angular MVVM concept, which seemlessly synchronise the view and the model.
Here we introduce an additional way of synchronisation, which is from the server to the model.

.. blockdiag::

    blockdiag {
      View <- Model <- Server;
    }

We use the message queue and the websocket interfaces to maintain synchronisation between the server and the client.

The client application just needs to query needed data using a highlevel API, and the data module is using the best approach to make the data always up to date.

Once the binding is setup by the controller, everything is automatically up-to-date.

Base Concepts
-------------

Collections
~~~~~~~~~~~
All the data you can get are Collections.
Even a query to a single resource returns a collection.
A collection is an Array subclass which has extra capabilities:

- It listen to the event stream and is able to maintain itself up-to-date
- It implements client side query in order to garantee up-to-date filtering, ordering and limiting queries.
- It has a fast access to each item it contains via its id.
- It has its own event handlers so that client code can react when the Collection is changing

Wrappers
~~~~~~~~
Each data type contain in a collection is wrapped in a javascript object.
This allows to create some custom enhancements to the data model.
For example the Change wrapper decodes the author name and email from the "author" field.

Each wrapper class also has specific access method, which allow to access more data from the REST hierachy.

.. blockdiag::

    blockdiag {
      data.getBuilds -> Collection -> Builds -> b.getSteps -> Collection -> Steps;
    }


Installation
~~~~~~~~~~~~

The Data module is available as a standalone AngularJS module.
Installation via bower:

  .. code-block:: sh

      bower install buildbot-data --save

It is recommended however for coherency to use the installation method via guanlecoja, in the bower section of guanlecoja/config.coffee:

  .. code-block:: coffee

    'bower':
        'deps':
            'buildbot-data':
                version: '~1.0.14'
                files: 'dist/buildbot-data.js'

Inject the ``bbData`` module to your application:

  .. code-block:: javascript

      angular.module('myApp', ['bbData'])


Service API
~~~~~~~~~~~

DataService
............

DataService is the service used for accessing the Buildbot data API.
It has a modern interface for accessing data in such a way that the updating of the data via web socket is transparent.

Methods:

``.open()``: returns a DataAccessor, which handles 3 way data binding

  * open a new accessor every time you need updating data in a controller
  * it registers on $destroy event on the scope, and thus automatically unsubscribes from updates when the data is not used anymore.

  .. code-block:: coffeescript

      # open a new accessor every time you need updating data in a controller
      class DemoController extends Controller
          constructor: ($scope, dataService) ->
              # automatically closes all the bindings when the $scope is destroyed
              data = dataService.open().closeOnDestroy($scope)

              # request new data, it updates automatically
              @builders = data.getBuilders(limit: 10, order: '-started_at')

``.getXs([id], [query])``: returns Collection which will eventually contain all the requested data

  * it's highly advised to use these instead of the lower level ``.get('string')`` function
  * ``Xs`` can be the following: ``Builds``, ``Builders``, ``Buildrequests``, ``Buildsets``, ``Workers``, ``Changes``, ``Changesources``, ``Forceschedulers``, ``Masters``, ``Schedulers``, ``Sourcestamps``
  * The collections returns without using an accessor are not automatically updated.
    So use those methods only when you know the data are not changing

  .. code-block:: coffeescript

      # assign builds to $scope.builds and then load the steps when the builds are discovered
      # onNew is called at initial load
      $scope.builds = dataService.getBuilds(builderid: 1)
      $scope.builds.onNew = (build) ->
          build.loadSteps()


``.get(endpoint, [id], [query])``: returns a <Collection>, when the promise is resolved, the Collection contains all the requested data

  .. code-block:: coffeescript

      # assign builds to $scope.builds once the Collection is filled
      builderid = 1
      $scope.builds = dataService.get("builders/#{builderid}/builds", limit: 1)
      $scope.builds.onNew = (build) ->
          build.loadSteps()

  .. code-block:: coffeescript

      # assign builds to $scope.builds before the Collection is filled using the .getArray() function
      $scope.builds = dataService.get('builds', builderid: 1)


``.control(url, method, [params])``: returns a promise, sends a JSON RPC2 POST request to the server

  .. code-block:: coffeescript

      # open a new accessor every time you need updating data in a controller
      dataService.control('forceschedulers/force', 'force').then (response) ->
          $log.debug(response)
      , (reason) ->
          $log.error(reason)

DataAccessor
............

DataAccessor object is returned by the dataService.open() method.

Methods:

``.closeOnDestroy($scope)``: registers scope destruction as waterfall destruction for all collection accessed via this accessor.

``.close()``: Destruct all collections previously accessed via this accessor.
    Destroying a collection means it will unsubscribe to any events necessary to maintain it up-to-date.

``.getXs([id], [query])``: returns Collection which will eventually contain all the requested data
   Same methods as in the dataService, except here the data will be maintained up-to-date.


Collections
...........

``.get(id)``: returns one element of the collection by id, or undefined, if this id is unknown to the collection.
   This method does not do any network access, and thus only know about data already fetched.

``.hasOwnProperty(id)``: returns true if this id is known by this collection.

``.close()``: forcefully unsubscribe this connection from auto-update.
   Normally, this is done automatically on scope destruction, but sometimes, when you got enough data, you want to save bandwith and disconnect the collection.

``.put(object)``: insert one plain object to the collection.
   As an external API, this method is only useful for the unit tests to simulate new data coming asynchronously.

``.from(object_list)``: insert several plain objects to the collection.
   This method is only useful for the unit tests to simulate new data coming asynchronously.

``.onNew = (object) ->``: Callback method which is called when a new object arrives in the collection.
  This can be called either when initial data is coming via REST api, or when data is coming via the event stream.
  The affected object is given in parameter.
  `this` context is the collection.

``.onUpdate = (object) ->``: Callback method which is called when an object is modified.
  This is called when data is coming via the event stream.
  The affected object is given in parameter.
  `this` context is the collection.

``.onChange = (collection) ->``: Callback method which is called when an object is modified.
  This is called when data is coming via the event stream.
  `this` context is the collection.
  The full collection is given in parameter (in case you override ``this`` via fat arrow).

Wrapper
.......

Wrapper objects are objects stored in the collection.
Those objects have specific methods, depending on their types. methods:

``.getXs([id], [query])``: returns a Collection, when the promise is resolved, the Collection contains all the requested data

  * same as ``dataService.getXs``, but with relative endpoint

  .. code-block:: coffeescript

      # assign builds to $scope.builds once the Collection is filled
      $scope.builds = dataService.getBuilds(builderid: 1)
      $scope.builds.onNew = (b) ->
          b.complete_steps = b.getSteps(complete:true)
          b.running_steps = b.getSteps(complete:false)

``.loadXs([id], [query])``: returns a Collection, the Collection contains all the requested data, which is also assigned to ``o.Xs``

  * ``o.loadXs()`` is equivalent to ``o.xs = o.getXs()``

  .. code-block:: coffeescript

      # get builder with id = 1
      dataService.getBuilders(1).onNew = (builder) ->
          # load all builds in builder.builds
          builder.loadBuilds().onNew (build) ->
              # load all buildsteps in build.steps
              build.loadSteps()

``.control(method, params)``: returns a promise, sends a JSON RPC2 POST request to the server
