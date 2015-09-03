### ###############################################################################################
#
#   This module contains all default configuration for the build process
#   Variables in this file can be overridden using the grunt/config.coffee file
#   located in the project directory
#
### ###############################################################################################
module.exports =

    name: "app"
    ### ###########################################################################################
    #   Directories
    ### ###########################################################################################
    dir:
        # The build folder is where the app resides once it's completely built
        build: 'static'
        # The coverage folder is where the files necessary for coverage, and the coverage report are stored
        coverage: 'coverage'
    ### ###########################################################################################
    #   This is a collection of file patterns
    ### ###########################################################################################
    files:

        # app entrypoint should be placed first, so need to be specific
        app: [
            'src/**/*.module.coffee'
        ]

        # scripts (can be coffee or js)
        scripts: [
            'src/**/*.coffee'
            '!src/**/*.spec.coffee'
        ]

        # CoffeeScript tests
        tests: [
            'test/**/*.coffee'
            'src/**/*.spec.coffee'
        ]

        # fixtures
        fixtures: [
            'test/**/*.fixture.*'
            'src/**/*.fixture.*'
        ]

        # Jade templates
        templates: [
            'src/**/*.tpl.jade'
        ]

        # Jade index
        index: [
            'src/app/index.jade'
        ]

        # Less stylesheets
        less: [
            'src/**/*.less'
        ]

        # Images
        images: [
            'src/**/*.{png,jpg,gif,ico}'
        ]

        # Fonts
        fonts: [
            'libs/font-awesome/fonts/*'
        ]
    bower:
        directory: "libs"
        # JavaScript libraries
        deps: {}
        testdeps: {}

    # Enable code coverage on coffeescript. ATM, this restricts you to CS 1.6, so you might want to disable it.
    coffee_coverage: true

    # produce a vendors.js file with the js dependancies. scripts.js will now only contain
    # you code logic (and optionally templates)
    vendors_apart: false

    # produce a templates.js file with all the jade templates in it.
    templates_apart: false

    # produce jade templates as js code, instead of html in angular's templatesCache
    # templates function will be available in templates_global
    templates_as_js: false
    templates_global: "TEMPLATES"

    # always produce a sourcemaps. This is useful for libs
    sourcemaps: false

    # configuration for the tasks. most of the tasks can be run independantly except for
    # bower, and karma which should be run respectively first and last
    preparetasks: "bower"
    buildtasks: ['scripts', 'styles', 'fonts', 'imgs',
        'index', 'tests', 'generatedfixtures', 'fixtures', 'vendors', 'templates']
    testtasks: "karma"

    generatedfixtures: ->

    ngclassify: (config) ->
        ->
            return {
                appName: config.name
                provider:
                    suffix: "Service"
                factory:
                    format: 'camelCase'
            }
    ### ###########################################################################################
    #   This is the default configuration for karma
    ### ###########################################################################################
    karma:
        # frameworks to use
        # available frameworks: https://npmjs.org/browse/keyword/karma-adapter
        frameworks: ['jasmine'],
        # test results reporter to use
        # possible values: 'dots', 'progress'
        # available reporters: https://npmjs.org/browse/keyword/karma-reporter
        reporters: ['progress'],
        # start these browsers
        # available browser launchers: https://npmjs.org/browse/keyword/karma-launcher
        browsers: ['PhantomJS'],
        files: ["scripts.js", 'generatedfixtures.js', 'fixtures.js', "tests.js"]
        logLevel: "LOG_DEBUG",

        plugins: [
          'karma-jasmine'
          'karma-phantomjs-launcher'
          'karma-sourcemap-loader'
          'karma-coverage'
        ],
        preprocessors: {
          '**/scripts.js': ['sourcemap']
          '**/tests.js': ['sourcemap']
        },
        coverageReporter:
            reporters: [
              type : 'html'
              dir: 'coverage'
            ,
              type : 'text'
            ]
