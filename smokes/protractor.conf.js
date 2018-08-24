const { SpecReporter } = require('jasmine-spec-reporter');

exports.config = {
    allScriptsTimeout: 11000,

    specs: [
        'e2e/*.scenarios.ts'
    ],

    SELENIUM_PROMISE_MANAGER: false,

    capabilities: {
        'browserName': 'chrome',
        chromeOptions: {
            // minimal supported browser size for tests
            // if smaller we start need to scroll for clicking buttons
            args: ['--window-size=1024,768']
        }
    },

    baseUrl: 'http://localhost:8010',

    framework: 'jasmine',

    jasmineNodeOpts: {
        defaultTimeoutInterval: 30000,
        print: function() {}
    },

    onPrepare() {
         jasmine.getEnv().addReporter(new SpecReporter({
             displayFailuresSummary: true,
             displayFailuredSpec: true,
             displaySuiteNumber: true,
             displaySpecDuration: true
         }));

        require('ts-node').register({
          project: './tsconfig.ee.json'
        });
    }
};
