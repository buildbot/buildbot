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
            build: 'buildbot_www'

        ### ###########################################################################################
        #   This is a collection of file patterns
        ### ###########################################################################################
        files:
            # Library files
            library:

                # JavaScript libraries. Which javascript files to include, from the
                # one downloaded by bower
                js: [
                    'src/libs/jquery/dist/jquery.js'
                    'src/libs/angular/angular.js'

                    'src/libs/angular-animate/angular-animate.js'
                    'src/libs/angular-bootstrap/ui-bootstrap-tpls.js'
                    'src/libs/angular-ui-router/release/angular-ui-router.js'
                    'src/libs/angular-recursion/angular-recursion.js'

                    'src/libs/lodash/dist/lodash.js'
                    'src/libs/moment/moment.js'
                    'src/libs/underscore.string/lib/underscore.string.js'
                    'src/libs/restangular/dist/restangular.js'
                ]

You can override more file patterns. See the defaultconfig.coffee for list of patterns available.
Normally, only the Javascript libraries are needed to configure.

create a ".bowerrc" with the configuration variables:

    {"directory": "src/libs"}

so that your bower dependencies are stored on side of your source code.
You also want to configure ".gitignore", to ignore this directory.

Use bower.json as usual to describe your javascript libraries dependancies. You at least need angular.js > 1.2, bootstrap 3.0 and jquery.

### Usage

2 gulp targets are created:

* ``gulp dev``: Use this for development. It will use require.js to load all the modules separatly. It will compile your coffeescript on the fly as you save them. This task only ends when you hit CTRL-C.

* ``gulp prod``: Use this for production. It will generate a ready for prod build of your application, with all the javascript concatenated and minified.

### Examples

Guanlecoja methodology has been built for the buildbot project, but is very generic, and can be used for any projects.

You can see it in action at https://github.com/buildbot/buildbot/tree/master/www
