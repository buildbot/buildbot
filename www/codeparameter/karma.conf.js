const common = require('buildbot-build-common');

module.exports = function karmaConfig (config) {
    common.createTemplateKarmaConfig(config, {
        testRoot: 'src/tests.webpack.js',
        webpack: require('./webpack.config')
    });
};
