
module.exports.createTemplateKarmaConfig = function(config, options) {
    config.set({
        frameworks: [
            'jasmine'
        ],

        reporters: [
            'progress',
            'coverage'
        ],

        files: [
            options.testRoot
        ],

        preprocessors: {
            [options.testRoot]: ['webpack', 'sourcemap']
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

        webpack: options.webpack,

        // Hide webpack build information from output
        webpackMiddleware: {
            noInfo: 'errors-only'
        },

        customLaunchers: {
            BBChromeHeadless: {
                base: 'ChromeHeadless',
                flags: [
                    '--headless',
                    '--disable-gpu',
                    '--no-sandbox',
                    '--window-size=1024,768',
                ],
            }
        },
    });
}
