'use strict';

const common = require('buildbot-build-common');
const env = require('yargs').argv.env;
const pkg = require('./package.json');

var event = process.env.npm_lifecycle_event;

var isTest = event === 'test' || event === 'test-watch';
var isProd = env === 'prod';

module.exports = function() {
    var basename = isProd ? pkg.name + '.min' : pkg.name;

    return common.createTemplateWebpackConfig({
        entry: {
            [basename]: './src/data.module.js',
        },
        libraryName: pkg.name,
        pluginName: pkg.plugin_name,
        dirname: __dirname,
        isTest: isTest,
        isProd: isProd,
        outputPath: __dirname + '/dist',
    });
}();
