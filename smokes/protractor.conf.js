exports.config = {
    allScriptsTimeout: 11000,

    specs: [
        'e2e/*.scenarios.ts'
    ],

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
        defaultTimeoutInterval: 30000
    },

    onPrepare() {
        require('ts-node').register({
          project: './tsconfig.ee.json'
        });
    }
};
