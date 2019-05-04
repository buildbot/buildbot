// Reference: http://karma-runner.github.io/0.12/config/configuration-file.html
module.exports = function karmaConfig (config) {
    config.set({
        frameworks: [
            'jasmine'
        ],

        reporters: [
            'progress',
            'coverage'
        ],

        files: [
            'src/tests.webpack.js'
        ],

        preprocessors: {
            'src/tests.webpack.js': ['webpack', 'sourcemap']
        },

        browsers: [
            'Chrome'
        ],

        singleRun: true,

        // Configure code coverage reporter
        coverageReporter: {
            dir: 'coverage/',
            reporters: [
                {type: 'text-summary'},
                {type: 'html'}
            ]
        },

        webpack: require('./webpack.config'),

        // Hide webpack build information from output
        webpackMiddleware: {
            noInfo: 'errors-only'
        }
    });
};
