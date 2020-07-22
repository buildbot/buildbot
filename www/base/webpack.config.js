'use strict';

const common = require('buildbot-build-common');
const env = require('yargs').argv.env;
const pkg = require('./package.json');
const WebpackShellPlugin = require('webpack-shell-plugin');
const WebpackCopyPlugin = require('copy-webpack-plugin');

var event = process.env.npm_lifecycle_event;

var isTest = event === 'test' || event === 'test-watch';
var isProd = env === 'prod';

module.exports = function() {
    const outputPath = __dirname + '/buildbot_www/static';
    return common.createTemplateWebpackConfig({
        entry: {
            scripts: './src/app/app.module.js',
            styles: './src/styles/styles.less',
        },
        libraryName: pkg.name,
        pluginName: pkg.plugin_name,
        dirname: __dirname,
        isTest: isTest,
        isProd: isProd,
        outputPath: outputPath,
        extractStyles: true,
        extraRules: [{
            test: /\.(ttf|eot|woff|woff2)(\?v=[0-9]\.[0-9]\.[0-9])?$/,
            use: 'file-loader'
        }, {
            test: /\.(jpe?g|png|svg|ico)(\?v=[0-9]\.[0-9]\.[0-9])?$/,
            use: [{
                loader: 'file-loader',
                options: {
                    name: '[name].[ext]',
                    outputPath: 'img'
                }
            }]
        }],
        extraPlugins: [
            new WebpackShellPlugin({
                onBuildEnd:['./node_modules/.bin/pug src/app/index.jade -o buildbot_www/static/']
            }),
            new WebpackCopyPlugin([
                {   from: './node_modules/outdated-browser-rework/dist/outdated-browser-rework.min.js',
                    to: outputPath + '/browser-warning.js'
                },
                {   from: './node_modules/outdated-browser-rework/dist/style.css',
                    to: outputPath + '/browser-warning.css'
                },
                {   from: './src/app/app.browserwarning.notranspile.js',
                    to: outputPath + '/browser-warning-list.js'
                },
            ]),
        ],
        provideJquery: true,
        supplyBaseExternals: true,
    });
}();
