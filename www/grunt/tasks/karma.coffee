### ###############################################################################################
#
#   Karma test runner
#   TODO fftest, chrometest, pjstest tasks?
#
### ###############################################################################################
module.exports =

    options:
        files: [
            '<%= dir.temp %>/scripts/test/main.js'
            {pattern: "<%= dir.temp %>/scripts/**/*.js", included: false}
            {pattern: "<%= dir.temp %>/scripts/**/*.js.map", included: false}
        ]
        preprocessors:
            '**/*.coffee' : ['coffee']
        coffeePreprocessor:
            options:
                sourceMap: true
        frameworks: ['jasmine', 'requirejs']
        # Possible values: 'dots', 'progress', 'junit', 'growl', 'coverage'
        reporters: ['progress']
        # Start these browsers, currently available:
        # - Chrome
        # - ChromeCanary
        # - Firefox
        # - Opera
        # - Safari (only Mac)
        # - PhantomJS
        # - IE (only Windows)
        browsers: ['PhantomJS']

    unit:
        options:
            browsers: ['PhantomJS']
            background: true
            keepalive: true
            autoWatch: false
            singleRun: false

    ci:
        options:
            singleRun: true