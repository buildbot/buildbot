'use strict';

// Modules
var webpack = require('webpack');
const env = require('yargs').argv.env;
var autoprefixer = require('autoprefixer');
var HtmlWebpackPlugin = require('html-webpack-plugin');
var ExtractTextPlugin = require('extract-text-webpack-plugin');
var CopyWebpackPlugin = require('copy-webpack-plugin');
const TerserPlugin = require('terser-webpack-plugin');
const pkg = require('./package.json');

var event = process.env.npm_lifecycle_event;

let libraryName = pkg.name;

var isTest = event === 'test' || event === 'test-watch';
var isProd = env === 'prod';

let mode;

if (isProd) {
    mode = 'production';
} else {
    mode = 'development';
}

module.exports = function makeWebpackConfig() {

    var config = {};

    config.entry = {
        waterfall: './src/module/main.module.js'
    };

    config.output = isTest ? {} : {
        path: __dirname + '/buildbot_wsgi_dashboards/static',
        filename: 'scripts.js',
        library: libraryName,
        libraryTarget: 'umd',
        umdNamedDefine: true,
        globalObject: "(typeof self !== 'undefined' ? self : this)",
    };

    config.optimization = {
        minimize: isProd,
        minimizer: [
            new TerserPlugin({
                cache: true,
                parallel: true,
                sourceMap: true,
                terserOptions: {
                    keep_classnames: true
                }
            }),
        ],
    };

    if (isTest) {
        config.devtool = 'inline-source-map';
    } else {
        config.devtool = 'source-map';
    }

    config.plugins = []

    if (!isTest) {
        config.externals = [
            'angular',
        ];
    }

    config.module = {
        rules: [{
            test: /\.js$/,
            loader: 'babel-loader',
            exclude: /node_modules/
        }]
    };

    if (isTest) {
        config.module.rules.push({
            enforce: 'pre',
            test: /\.js$/,
            exclude: [
                /node_modules/,
                /\.spec\.js$/
            ],
            loader: 'istanbul-instrumenter-loader',
            query: {
                esModules: true
            }
        })
    }

    return config;
}();
