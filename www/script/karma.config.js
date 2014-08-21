// Karma configuration
// Generated on Mon Jun 16 2014 16:33:22 GMT+0200 (Romance Daylight Time)
/*global module, config*/
module.exports = function (config) {
    "use strict";

    config.set({

        // base path that will be used to resolve all patterns (eg. files, exclude)
        basePath: '',


        // frameworks to use
        // available frameworks: https://npmjs.org/browse/keyword/karma-adapter
        frameworks: ['jasmine', 'requirejs'],


        // list of files / patterns to load in the browser
        files: [
            'test/test-main.js',
            {pattern: 'libs/**/*.js', included: false},
            {pattern: 'plugins/**/*.js', included: false},
            {pattern: 'project/**/*.js', included: false},
            {pattern: 'test/*.js', included: false},
            {pattern: 'test/*.html', included: false, served: true},
            {pattern: 'templates/**/*.mustache', included: false, served: true},
            {pattern: 'templates/**/*.handlebars', included: false, served: true},
            {pattern: 'templates/**/*.hbs', included: false, served: true},
            {pattern: 'text.js', included: false, served: true}
        ],


        // list of files to exclude
        exclude: [
        ],


        // preprocess matching files before serving them to the browser
        // available preprocessors: https://npmjs.org/browse/keyword/karma-preprocessor
        preprocessors: {
            'templates/**/*.mustache': [''],
            'templates/**/*.handlebars': [''],
            'project/*.js': ['coverage']
        },

        // test results reporter to use
        // possible values: 'dots', 'progress'
        // available reporters: https://npmjs.org/browse/keyword/karma-reporter
        reporters: ['progress'],


        // web server port
        port: 9876,


        // enable / disable colors in the output (reporters and logs)
        colors: true,


        // level of logging
        // possible values: config.LOG_DISABLE || config.LOG_ERROR || config.LOG_WARN || config.LOG_INFO || config.LOG_DEBUG
        logLevel: config.LOG_INFO,


        // enable / disable watching file and executing tests whenever any file changes
        autoWatch: false,


        // start these browsers
        // available browser launchers: https://npmjs.org/browse/keyword/karma-launcher
        browsers: ['Chrome'],


        // Continuous Integration mode
        // if true, Karma captures browsers, runs the tests and exits
        singleRun: false
    });
};
