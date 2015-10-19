# guanlecoja: opinionated RAD build environment for single page web apps

It integrates several web technologies and methodologies together to accelerate web development.

- Gulp: build tool
- Angularjs: MVC framework
- Less: CSS preprocessor
- Coffee-script: Javascript language
- Jade: template engine
- Bootstrap: css framework
- bower: js library

Gulp is a nice and generic tool for creating build system. Its available plug-ins are evolving
fast so each time a new plug-in is changing the game you have to update all your projects
in order to use it.

Guanlecoja is made to solve this problem. just make your web app depend on "latest"
version of Guanlecoja, and the greatest build tools will automatically be synchronized.

In order to make this promise, Guanlecoja needs to make some decision for you.
This is why it defines the languages and framework you use, and the organization of your project.

Guanlecoja best practices are well described in https://medium.com/@dickeyxxx/266c1a4a6917

### QuickStart

Yeoman generator is created to easily bootstrap a guanlecoja app

    npm install -g generator-guanlecoja
    yo guanlecoja
    # answer questions..
    gulp dev

Advantage compared with other yeoman generators is that build system is managed in an external npm module
so it will be upgraded automatically when new versions are coming using normal npm commands

### Why the name ``guanlecoja``

Because it sounds much better than gulp-angular-less-coffee-jade

### Configuration

Make your package.js depend on "guanlecoja"

    npm install guanlecoja --save-dev

create a gulpfile.js with only following line:

    require("guanlecoja")(require("gulp"))

create a "guanlecoja/config.coffee" with the configuration variables:

    ### ###############################################################################################
    #
    #   This module contains all configuration for the build process
    #
    ### ###############################################################################################
    config =

        ### ###########################################################################################
        #   Directories
        ### ###########################################################################################
        dir:
            # The build folder is where the app resides once it's completely built
            build: 'static'


    ### ###########################################################################################
    #   Bower dependencies configuration
    ### ###########################################################################################
        bower:
            # JavaScript libraries (order matters)
            deps:
                jquery:
                    version: '~2.1.1'
                    files: 'dist/jquery.js'
                angular:
                    version: '~1.2.11'
                    files: 'angular.js'
            testdeps:
                "angular-mocks":
                    version: ANGULAR_TAG
                    files: "angular-mocks.js"
    module.exports = config

#### config details:

* `name`: name of the module. If it is not app, then the views will have their own namespace "{name}/views/{viewname}"

* `dir`: directories configuration
* `dir.build`: directories where the build happen. There is no intermediate directory, and this points to the final destination of built files.
* `dir.coverage`: directory where coverage results are output

* `files`: file glob specifications. This is a list of globs where to find files of each types. Normally defaults are good enough

* `files.app`(list of globs): angular.js modules. Those have to be loaded first
* `files.scripts`(list of globs): application scripts source code. Can be coffee or JS. built in `script.js`
* `files.tests`(list of globs): tests source code. Can be coffee or JS. built in `tests.js`
* `files.fixtures`(list of globs): fixtures for tests. Those fixtures can be json files, or text files, are built in `tests.js`, and populated in window.FIXTURES global variable in the test environment.
* `files.templates`(list of globs): references the templates. All the templates are built in `scripts.js`, and loaded automatically in angularjs's template cache.
* `files.index`: references the jade file that generates main `index.htm` entrypoint for your SPA. Your index.jade should load built `scripts.js`, and `styles.css`
* `files.less`: references the less files. By default they can be anywhere in the source code, and are concatenated in styles.css. Order is undefined, so make sure to not have order dependent styling.
* `files.images`: those images are just copied to `#{config.dir.build}/img`
* `files.fonts`: those fonts are just copied to `#{config.dir.build}/fonts`

* `bower`: gulp-bower-deps configuration
* `bower.directory`: directory where js dependencies should be stored locally
* `bower.deps`: object describing the list of js dependencies for your application. js files are concatenated either in script.js or vendor.js according to the vendors_apart configuration
* `bower.deps.#{name}`: keys of the deps object are the registered bower package names
* `bower.deps.#{name}.version`: version descriptor of the bower package.list
* `bower.deps.#{name}.files`: list of files relative to package installation directory, that guanlecoja will include.
* `bower.testdeps`: same format as `bower.deps`, but those packages will only be included in test environment.

* `coffee_coverage`(boolean): Enable code coverage on coffeescript. At the moment, this restricts you to CS 1.6, so you might want to disable it. It is anyway only used when building with --coverage
* `vendors_apart`(boolean): Put the vendor scripts apart in a `vendor.js` file. Putting third party code apart can help doing better cache control when your app is continuously deployed.
* `templates_apart`(boolean): Put the template cache in another file.
* `templates_as_js`(boolean): Compile the templates as client side templates (needs jade-runtime.js bower dependency).
* `sourcemaps`(boolean): Force generation of sourcemaps even in prod mode. This is useful if you are using guanlecoja to build libs (e.g. guanlecoja.ui)

* `preparetasks`(list of strings): list of tasks to do before building (like fetching bower)
* `buildtasks`(list of strings): list of tasks for build (everything is made in parallel)
* `testtasks`(list of strings): list of tasks for testing (done after buildtasks)

* `generatedfixtures`(function): customizing endpoint for generating the fixtures
* `ngclassify`(function): customizing endpoint for ngClassify, directly passed to gulp-ngclassify
* `karma`(object): customized options for karma. See karma documentation for more information.

### Usage

2 gulp targets are created:

* ``gulp dev``: Use this for development. It will use require.js to load all the modules separatly. It will compile your coffeescript on the fly as you save them. This task only ends when you hit CTRL-C.

* ``gulp prod``: Use this for production. It will generate a ready for prod build of your application, with all the javascript concatenated and minified.

#### --notests

In some environments where it is hard to install phantomjs, or setup xvfb (old systems, or Paas build environment), it might be suitable to just not run the tests, and only run the build part. In those case, just run:

```
gulp prod --notests
```

### Debugging via sourcemaps.

``gulp dev`` enable sourcemaps. This is a modern technique to map the compiled javascript to the original coffee-script tree.
Just enable sourcemaps into your browser. (its in Chrome Dev Tools's Setting panel)
Full source code is actually embedded in the scripts.js.map

### Live Reloading

You will need to install RemoteLiveReload extension:
https://chrome.google.com/webstore/detail/remotelivereload/jlppknnillhjgiengoigajegdpieppei

This extension only works when you are testing on the same machine where gulp is running, using port 35729.
If you really care about developing on a remote machine, you can always forward the 35729 port.

### Code Coverage

Code Coverage is a technique that tells you how much of your code is run during the unit tests. Achieving coverage of 100% is a good metric to tell the quality of you unit tests, and that the code does not have a corner case typo.

``gulp --coverage`` enables code coverage report using ibrik coffeescript coverage annotation engine.
This will create a ``coverage`` directory with the report inside it.

#### Caveats:

Ibrik uses the coffeescript-redux compiler, which understands slightly different coffeescript. most notable known issues are:

* It does not supports CS1.7 (e.g. parenthese-less call chaining)
* class without constructor will fail due to a bug in Ibrik: https://github.com/Constellation/ibrik/issues/21

### Examples

Guanlecoja methodology has been built for the buildbot project, but is very generic, and can be used for any projects\.

You can see it in action at https://github.com/buildbot/buildbot/tree/master/www

### ChangeLog

* 0.4.2: update gulp-bower-deps to retry after cleaning up the lib directory
* 0.4.1: Do not uglyfy vendor.js. Some vendors actually fail to run properly when uglified
* 0.4.0: upgrade dependencies, and reintroduce browserify optimization
* 0.3.7: revert Prebuild most of the dependencies. Was not stable enough
* 0.3.6: Prebuild most of the dependencies. node_modules dir is now  100MB smaller
* 0.3.5: doc update with yo support
* 0.3.4: fix error handling due to api change from gulp-if
* 0.3.2: add help screen
* 0.3.1: add --notests option
* 0.2.11: fix issue when karma is not specified in config.coffee
* 0.2.10: fix issue with tests.js first in karma.files
* 0.2.9: fix problem when no bower deps
* 0.2.8: add support for coverage
* 0.2.7: revert connect to 2.x
* 0.2.4: small ngClassify default config enhancement
* 0.2.3: bump ng-classify for better multi module support, hardcode angular-template-cache, waiting my PR is merged
* 0.2.2: add optional server, handle errors correctly in watch mode
* 0.2.1: doc update
* 0.2.0: better defaults, add support for automatic bower dependancy fetching
