'use strict';

const common = require('buildbot-build-common');
const env = require('yargs').argv.env;
const pkg = require('./package.json');
const WebpackShellPlugin = require('webpack-shell-plugin');

var event = process.env.npm_lifecycle_event;

var isTest = event === 'test' || event === 'test-watch';
var isProd = env === 'prod';

module.exports = function() {
    return common.createTemplateWebpackConfig({
        entry: {
            scripts: './src/app/app.module.js',
            styles: './src/styles/styles.less',
        },
        libraryName: pkg.name,
        dirname: __dirname,
        isTest: isTest,
        isProd: isProd,
        outputPath: __dirname + '/buildbot_www/static',
        extractStyles: true,
        extraRules: [{
            test: /\.(ttf|eot|svg|woff|woff2)(\?v=[0-9]\.[0-9]\.[0-9])?$/,
            use: 'file-loader'
        }],
        extraPlugins: [
            new WebpackShellPlugin({
                onBuildEnd:['./node_modules/.bin/pug src/app/index.jade -o buildbot_www/static/']
            }),
        ],
        provideJquery: true,
        supplyBaseExternals: true,
    });
}();
