# angular-www
buildbot web ui built with coffeescript and angularjs
nodejs ecosystem is widely used to build the app: coffeescript, requirejs, less, grunt, jade templates
the app needs to built before running, but there are tools to build the app upon file change (grunt dev)

See rest of the readme for original explainations from AngularFun
Compared to angularfun, we:

* drop the original nodejs server code
* change build directory to "built" instead of "dist" which is already used by python setuptools.
* use jade as a template's syntax sugar

See doc at ../master/docs

based on:
# AngularFun
*By [@CaryLandholt](https://twitter.com/carylandholt)*

## About
AngularFun is an [AngularJS](http://angularjs.org/) large application Reference Architecture.  The intent is to provide a base for creating your own AngularJS applications with minimal boilerplate setup and ceremony.

Simply follow the patterns and you'll get a complete development workflow, including:

* file organization
* compilation of [CoffeeScript](http://coffeescript.org/) files
* compilation of [LESS](http://lesscss.org/) files
* three build configurations
	* **default** - compilation with no optimizations
	* **dev** - compilation with no optimizations but includes file watching to monitor changes and build changed files on-the-fly
	* **prod** - compilation with all optimizations, including concatenation and minification of JavaScript, CSS, and HTML
* full dependency management (file loading and dependency resolution)
* an in-browser unit testing strategy

## Prerequisites
* Must have [Git](http://git-scm.com/) installed
* Must have [node.js (at least v0.8.1)](http://nodejs.org/) installed with npm (Node Package Manager)
* Must have [CoffeeScript](https://npmjs.org/package/coffee-script) node package installed globally.  `npm install -g coffee-script`
* Must have [Grunt](https://github.com/gruntjs/grunt) node package installed globally.  `npm install -g grunt`

## Install Angular Fun
Enter the following commands in the terminal.

1. `git clone git://github.com/CaryLandholt/AngularFun.git`
2. `cd AngularFun`
3. `npm install`

## Compile Angular Fun
You have three options.

1. `grunt` - will compile the app preserving individual files (when run, files will be loaded on-demand)
2. `grunt dev` - same as `grunt` but will watch for file changes and recompile on-the-fly
3. `grunt prod` - will compile using optimizations.  This will create one JavaScript file and one CSS file to demonstrate the power of [r.js](http://requirejs.org/docs/optimization.html), the build optimization tool for RequireJS.  And take a look at the index.html file.  Yep - it's minified too.

## Making Changes
* `grunt dev` will watch for any CoffeeScript (.coffee), Less (.less), or .template file changes.  When changes are detected, the files will be linted, compiled, and ready for you to refresh the browser.

## Running Tests
You have two options.

1. [Jasmine](http://pivotal.github.com/jasmine/) HTML runner -  run `grunt` - Then open /test/runner.html in your browser to run the unit tests using Jasmine.
2. [Testacular](http://vojtajina.github.com/testacular/) - `grunt test` -  Defaults to running the tests in chrome, but you can easily change this in testacular.conf.js browsers section as required.

## Commentary
AngularFun is a by-product of my learning AngularJS and became the reference architecture to my day job project, a very large internally and externally-facing application with extensive user interactions.

I needed something that could support our Architecture Principles, including scale, stability, and maintenance.

My background with using [RequireJS](http://requirejs.org/), see the [RequireJS screencasts](http://www.youtube.com/watch?v=VGlDR1QiV3A&list=PLCBD579A7ADB6313A) on my [YouTube channel](http://www.youtube.com/user/carylandholt), enabled me to get up and running with managing many individual files right away.  RequireJS is a terrific dependency management technology.

### Take 1
Here's an early example controller in CoffeeScript.

```CoffeeScript
define ['controllers/controllers', 'services/gitHubService'], (controllers) ->
	controllers.controller 'gitHubController', ['$scope', '$location', 'gitHubService', ($scope, $location, gitHubService) ->
		$scope.search = (searchTerm) ->
			$location.path "/github/#{searchTerm}"

		$scope.onRouteChange = (routeParams) ->
			$scope.searchTerm = routeParams.searchTerm

			gitHubService.get $scope.searchTerm
			, (repos) ->
				$scope.repos = repos
	]
```

There are a couple things going on here.  RequireJS is loading controllers/controllers and services/gitHubService and providing a handle to both.
The controllers module was an early attempt at organizing AngularJS functionality into separate AngularJS modules (i.e. controllers, services, directives, filters, and responseInterceptors).
This ultimately provided no benefit, so I got rid of them.  They were just noise.

### Take 2
Using only one AngularJS module and rewriting the above script without the functionality-specific AngularJS container modules we have:

```CoffeeScript
define ['libs/angular', 'services/gitHubService'], (angular) ->
	angular.module('app').controller 'gitHubController', ['$scope', '$location', 'gitHubService', ($scope, $location, gitHubService) ->
		$scope.search = (searchTerm) ->
			$location.path "/github/#{searchTerm}"

		$scope.onRouteChange = (routeParams) ->
			$scope.searchTerm = routeParams.searchTerm

			gitHubService.get $scope.searchTerm
			, (repos) ->
				$scope.repos = repos
	]
```

As you can see, I now had to bring in a reference to libs/angular.  This *was* a dependency for controllers/controllers.

Let's now focus on the gitHubService dependency.  The file needs to be loaded, of course, but RequireJS doesn't need to provide a handle to it since AngularJS will do that part.  Notice there's no gitHubService parameter in the define callback.

But something just didn't sit well with me.  RequireJS will load dependent files and provide a handle to them beautifully; however, AngularJS has its own dependency management system.  But there is a difference.

AngularJS does not load dependent files, but it will provide a handle to them once they *are* loaded.  RequireJS does both.

So the define function is making sure AngularJS is loaded and provides a handle to it, even though it's a global variable.  It also makes sure gitHubService is loaded but doesn't need to provide a handle since the AngularJS dependency management system will do this.

Even though there is a difference, there is some overlap in responsibility here.  This can be observed with the mere fact that there is a gitHubService dependency referenced in the define function as well as the controller function.  So the developer has to work in the RequireJS world and AngularJS world in the same file.

### Take 3

So I decided to refactor the files and remove RequireJS completely, at least from the individual files.

Now we have:

```CoffeeScript
angular.module('app').controller 'gitHubController', ['$scope', '$location', 'gitHubService', ($scope, $location, gitHubService) ->
	$scope.search = (searchTerm) ->
		$location.path "/github/#{searchTerm}"

	$scope.onRouteChange = (routeParams) ->
		$scope.searchTerm = routeParams.searchTerm

		gitHubService.get $scope.searchTerm
		, (repos) ->
			$scope.repos = repos
]
```

To me, this just feels better.  The file contains only AngularJS business.  Albeit, I did choose to use a single AngularJS application module called **app** and accept the use of the angular global variable.

So if we've removed RequireJS from the files, how do we load the files to let AngularJS do its thing?

I really don't care for including multiple script references in the index.html file, such as:

```html
<!-- angular must load first -->
<script src="/scripts/libs/angular.js"></script>

<!-- angular dependencies must load next -->
<script src="/scripts/libs/angular-resource.js"></script>
<script src="/scripts/app.js"></script>
<script src="/scripts/services/messageService.js"></script>
<script src="/scripts/services/gitHubService.js"></script>
<script src="/scripts/controllers/gitHubController.js"></script>
<!-- ... more scripts -->

<!-- bootstrap must load last -->
<script src="/scripts/bootstrap.js"></script>
```

Although this may be suitable for some, I'm not comfortable with ensuring load order by where the script references are placed (the angular script reference must precede angular-resource, for example).  I prefer to be more prescriptive than that.
And we also need to concatenate and minify the scripts for our prod build.  We could grep the script references, concatenate, and then minify.  We could try out [Yeoman](http://yeoman.io/).  This all seemed a bit heavy-handed.

This is where the RequireJS [shim](http://requirejs.org/docs/api.html#config-shim) configuration comes in.

Since we no longer have dependencies referenced in individual files by way of RequireJS, and the multiple script reference idea is unappealing, we can define our dependencies inside our main file using shim.  Notice the dependencies can be referenced in any order.  RequireJS will ensure dependencies are loaded prior to their being required.

```CoffeeScript
require
	shim:
		'controllers/gitHubController': deps: ['libs/angular', 'app', 'services/gitHubService']
		'libs/angular-resource': deps: ['libs/angular']
		'services/gitHubService': deps: ['libs/angular', 'app', 'libs/angular-resource', 'services/messageService']
		'services/messageService': deps: ['libs/angular', 'app']
		'app': deps: ['libs/angular', 'libs/angular-resource']
		'bootstrap': deps: ['libs/angular', 'app']
	[
		'require'
		'controllers/gitHubController'
	], (require) ->
		require ['bootstrap']
```

The bootstrap file is requested within the callback since it must load last.

Now we only need a single script reference inside index.html.

```html
<script data-main="/scripts/main.js" src="/scripts/libs/require.js"></script>
```

So what about concatenation and minification?

Since we're only using RequireJS to manage load order, we can leverage the RequireJS optimizer to concatenate and minify too.  And once the files are concatenated and minified to a single file, we no longer need RequireJS.  This is perfect for our prod build.

We do, however, need to introduce a condition in index.html to use the non-optimized files or the optimized files based on the build environment.  The build will do it for us.

Here are the final index.html script references.  Note that the condition will not be part of the final output.

```html
<% if (config.environment === 'prod') { %>
	<script src="/scripts/scripts.min.js %>"></script>
<% } else { %>
	<script data-main="/scripts/main.js" src="/scripts/libs/require.js"></script>
<% } %>
```

### Give and Take
After many iterations it now feels right.  All [comments and questions](https://github.com/CaryLandholt/AngularFun/issues) and [Pull Requests](https://github.com/CaryLandholt/AngularFun/pulls) are always welcome.  I respond to all.

## To-Do
* Add many more unit tests :(
* Add more documentation :(
* Screencasts :)
