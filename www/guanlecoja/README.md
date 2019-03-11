[![Travis](https://img.shields.io/travis/buildbot/guanlecoja.svg)](https://travis-ci.org/buildbot/guanlecoja)
[![npm](https://img.shields.io/npm/v/guanlecoja.svg)](https://www.npmjs.com/package/guanlecoja)
[![node](https://img.shields.io/badge/nodejs-0.11%2C0.12%2C4.1%2C4.2%2C5.1%2C5.2%2C5.3-green.svg)](https://nodejs.org)

# guanlecoja: opinionated RAD build environment for single page web apps

It integrates several web technologies and methodologies together to accelerate web development.

- Gulp: build tool
- Angularjs: MVC framework
- Less: CSS preprocessor
- Coffee-script: Javascript language
- pug: template engine (formerly known as jade)
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

Please look at the default config option to see how guanlecoja is configured by default.

https://github.com/buildbot/guanlecoja/blob/master/defaultconfig.coffee

#### config details:

* `name`: name of the module. If it is not app, then the views will have their own namespace "{name}/views/{viewname}"

* `dir`: directories configuration
* `dir.build`: directories where the build happen. There is no intermediate directory, and this points to the final destination of built files.
* `dir.coverage`: directory where coverage results are output
* `output_scripts`: filename for the output concatenated scripts
* `output_vendors`: filename for the output concatenated vendors
* `output_templates`: filename for the output concatenated templates
* `output_tests`: filename for the output concatenated tests
* `output_styles`: filename for the output concatenated css

* `files`: file glob specifications. This is a list of globs where to find files of each types. Normally defaults are good enough

* `files.app`(list of globs): angular.js modules. Those have to be loaded first
* `files.scripts`(list of globs): application scripts source code. Can be coffee or JS. built in `script.js`
* `files.tests`(list of globs): tests source code. Can be coffee or JS. built in `tests.js`
* `files.fixtures`(list of globs): fixtures for tests. Those fixtures can be json files, or text files, are built in `tests.js`, and populated in window.FIXTURES global variable in the test environment.
* `files.templates`(list of globs): references the templates. All the templates are built in `scripts.js`, and loaded automatically in angularjs's template cache.
* `files.index`: references the pug/jade file that generates main `index.htm` entrypoint for your SPA. Your index.pug should load built `scripts.js`, and `styles.css`
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
* `devserver.port`: the port used for the developement server

### Usage

2 gulp targets are created:

* ``gulp dev``: Use this for development. It will use require.js to load all the modules separately. It will compile your coffeescript on the fly as you save them. This task only ends when you hit CTRL-C.

* ``gulp prod``: Use this for production. It will generate a ready for prod build of your application, with all the javascript concatenated and minified.

### NPM 3

Guanlecoja supports npm3 in experimental mode. Please report issues if you have a problem.

#### --notests

In some environments where it is hard to install Chrome or Chromium 59+, it might be suitable to just not run the tests, and only run the build part. In those case, just run:

```
gulp prod --notests
```

### Testing with Karma

Testing with karma is completely integrated in gulp with guanlecoja.
You shouldn't need to understand or configure karma, it should work out of the box using convention over configuration principles.

Tests are found automatically using `the files.tests` configuration, which usually maps to tests/** and src/**/*.spec.coffee.
So you should place your test framework code in tests/*, and your spec files aside from the actual tested code:

    \
    |- tests/
    |       |- backend_mock.service.coffee
    |- src/
    |      |services/
    |              |- my.service.coffee
    |              |- my.service.spec.coffee
    |- src/
    |     |pages/
    |           | home/
    |                  |- home.controller.coffee
    |                  |- home.controller.spec.coffee
    |                  |- home.tpl.jade

The test scripts are all concatenated into a tests.js script, along with the dependencies defined in `bower.testdeps` and karma will run that script after the other normal scripts.

You can configure the order the scripts are loaded using configuration:

    karma.files: ['generatedfixtures.js', 'fixtures.js', "tests.js", "scripts.js"]

In this example, we are loading scripts.js last. This is useful when testing libraries, where scripts.js does not contain the necessary (e.g angular.js) dependencies.
In that case, we rather include the dependencies in tests.js, and thus need to run it first in the karma environment.

Karma as configured by default by guanlecoja requires Chrome/Chromium >= 59, for its headless feature.

#### Testing in CI

CI servers may need different configuration of browsers.
if the "CI" environment variable is set, then guanlecoja will substitute the karma config "browsers" with the content of "browsers_ci", by default, this will run chrome headless with the --no-sandbox option.
https://github.com/travis-ci/travis-ci/issues/2555

### Bower dependencies

guanlecoja allows you to define your bower dependencies directly into the guanlecoja/config.coffee file.
It will automatically download latest version, and embed the dependencies into your script.js file.

guanlecoja will create BOWERDEPS global variable that contains the list of packages that have been included in your project as long as metadata of which version, and what is the homepage of the package.

Note that the BOWERDEPS variable is shared between all modules that use guanlecoja as build system, this will contain deps of deps.

### Development server

For standalone UI, development server is given as a simple helper.
Just setup the parameter `devserver.port: 8080`, and use the `server` gulp task:

    # gulp dev server
    [...]

The `dir.build` will then be exposed to http://localhost:8080/

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

``gulp --coverage`` enables code coverage report using coffeescript coverage annotation engine.
This will create a ``coverage`` directory with the report inside it.

### Examples

Guanlecoja methodology has been built for the buildbot project, but is very generic, and can be used for any projects\.

You can see it in action at https://github.com/buildbot/buildbot/tree/master/www

### ChangeLog

* 0.9.1: Upgrade dependencies. Remove Browserify hack. It does not work anymore, and is not needed as much with yarn improvements
* 0.8.8: Upgrade dependencies
* 0.8.7: revert usage of gulp-watch as it does not work as expected.
* 0.8.6: fix high CPU usage in dev mode. Use ChromeHeadless by default.
* 0.8.5: screwed-up release.
* 0.8.4: Properly configure chrome headless if the CI environment is found.
* 0.8.3: switch to chrome for testing. phantomjs has been deprecated.
* 0.8.2: bump gulp-sass version for node 7.10 support.
* 0.8.1: Some jade->pug fixes. beware that with jade-pug the default extension is .pug so extends "layout" will look for layout.pug
         You can just rename your layout file or extend with explicit file extension
* 0.8.0: upgrade dependencies. (gulp-minify-css -> gulp-clean-css,  gulp-jade -> gulp-pug). Fix node dependencies to make yarn work.
* 0.7.2: upgrade gulp-if: fixes issue with node6
* 0.7.0: upgrade gulp-bower-deps. This gives you BOWERDEPS global variable
* 0.6.2: fix and upgrade phantomjs to 2.1.1. This will help on the stability of the builds.
* 0.6.1: Support sass include PATH to be implicitly set as includePath. fix problem with impossibility to create a task after karma
* 0.5.5: update dependencies for npm 3
* 0.5.4: add more documentation on the testing methodology
* 0.5.3: fix problem with generated packages does not work with symlink
* 0.5.2: travis test against node 5.
* 0.5.1: mark it does not support npm>3. Peer dependencies were removed, and directories are flatten. Need more time to fix it correctly
* 0.5.0: make output configurable
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
