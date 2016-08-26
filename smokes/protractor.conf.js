exports.config = {
    allScriptsTimeout: 11000,

    specs: [
        'e2e/*.scenarios.coffee'
    ],

    capabilities: {
        'browserName': 'phantomjs'
    },

    baseUrl: 'http://localhost:8010',

    framework: 'jasmine',
 
    jasmineNodeOpts: {
        defaultTimeoutInterval: 30000
    }
};
