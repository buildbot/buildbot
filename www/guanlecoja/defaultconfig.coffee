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


    preparetasks: "bower"
    buildtasks: ['scripts', 'styles', 'fonts', 'imgs',
        'index', 'tests', 'generatedfixtures', 'fixtures']
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
          'karma-jasmine',
          'karma-phantomjs-launcher',
          'karma-sourcemap-loader'
        ],
        preprocessors: {
          '**/*.js': ['sourcemap']
        },
