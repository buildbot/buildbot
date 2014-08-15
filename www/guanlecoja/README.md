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

Guanlecoja best practices are well descibed in https://medium.com/@dickeyxxx/266c1a4a6917

### yo

Well known tool Yeoman has similar goals, but it does not provide automatic update of the tools.
Only templates and boilerplate generation is done, with no way of upgrading your project.

yo templates using Guanlecoja maybe created in the future

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
    module.exports =

        ### ###########################################################################################
        #   Directories
        ### ###########################################################################################
        dir:
            # The build folder is where the app resides once it's completely built
            build: 'static'


    ### ###########################################################################################
    #   Bower dependancies configuration
    ### ###########################################################################################
    bower:
        # JavaScript libraries (order matters)
        deps:
            jquery:
                version: '~2.1.1'
                files: 'dist/jquery.js'
            angular:
                version: ANGULAR_TAG
                files: 'angular.js'
            "angular-animate":
                version: ANGULAR_TAG
                files: 'angular-animate.js'
            "angular-bootstrap":
                version: '~0.11.0'
                files: 'ui-bootstrap-tpls.js'
            "angular-ui-router":
                version: '~0.2.10'
                files: 'release/angular-ui-router.js'
            lodash:
                version: "~2.4.1"
                files: 'dist/lodash.js'
            'underscore.string':
                version: "~2.3.3"
                files: 'lib/underscore.string.js'
            "font-awesome":
                version: "~4.1.0"
                files: []
            "bootstrap":
                version: "~3.1.1"
                files: []
        testdeps:
            "angular-mocks":
                version: ANGULAR_TAG
                files: "angular-mocks.js"

You can override more file patterns. See the defaultconfig.coffee for list of patterns available.
Normally, only the Javascript libraries are needed to configure.

create a ".bowerrc" with the configuration variables:

    {"directory": "libs"}

so that your bower dependencies are stored on side of your source code.
You also want to configure ".gitignore", to ignore this directory.

Use bower.json as usual to describe your javascript libraries dependancies. You at least need angular.js > 1.2, bootstrap 3.0 and jquery.

### Usage

2 gulp targets are created:

* ``gulp dev``: Use this for development. It will use require.js to load all the modules separatly. It will compile your coffeescript on the fly as you save them. This task only ends when you hit CTRL-C.

* ``gulp prod``: Use this for production. It will generate a ready for prod build of your application, with all the javascript concatenated and minified.


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

* 0.2.8: add support for coverage
* 0.2.7: revert connect to 2.x
* 0.2.4: small ngClassify default config enhancement
* 0.2.3: bump ng-classify for better multi module support, hardcode angular-template-cache, waiting my PR is merged
* 0.2.2: add optional server, handle errors correctly in watch mode
* 0.2.1: doc update
* 0.2.0: better defaults, add support for automatic bower dependancy fetching
