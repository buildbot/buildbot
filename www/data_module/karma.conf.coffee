module.exports = (config) ->
    config.set
        # Base path, that will be used to resolve files and exclude
        basePath: ''

        # Testing framework to use (jasmine/mocha/qunit/...)
        frameworks: ['jasmine']

        # List of files / patterns to load in the browser
        files: [
            'libs/tabex/dist/tabex.js'
            'libs/dexie/dist/latest/Dexie.js'
            'libs/angular/angular.js'
            'libs/angular-mocks/angular-mocks.js'
            'src/**/*.module.coffee'
            'src/**/*.coffee'
        ]

        # List of files / patterns to exclude
        exclude: []

        # Web server port
        port: 9876

        # Level of logging
        # Possible values: LOG_DISABLE || LOG_ERROR || LOG_WARN || LOG_INFO || LOG_DEBUG
        logLevel: config.LOG_INFO

        # Start these browsers, currently available:
        # - Chrome
        # - ChromeCanary
        # - Firefox
        # - Opera
        # - Safari (only Mac)
        # - PhantomJS
        # - IE (only Windows)
        browsers: [
          'PhantomJS'
        ]

        # Continuous Integration mode
        # enable / disable watching file and executing tests whenever any file changes
        autoWatch: false
        singleRun: true

        colors: true

        preprocessors: '**/*.coffee': ['ng-classify', 'coffee']

        ngClassifyPreprocessor:
            options:
                # any options supported by ng-classify
                # https://github.com/CaryLandholt/ng-classify#api
                appName: 'bbData'
                provider:
                    suffix: 'Service'
