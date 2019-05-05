'use strict';

// Modules
var path = require('path');
var webpack = require('webpack');
const env = require('yargs').argv.env;
var autoprefixer = require('autoprefixer');
var HtmlWebpackPlugin = require('html-webpack-plugin');
var ExtractTextPlugin = require('extract-text-webpack-plugin');
var CopyWebpackPlugin = require('copy-webpack-plugin');
const MiniCssExtractPlugin = require('mini-css-extract-plugin');
const TerserPlugin = require('terser-webpack-plugin');
const FixStyleOnlyEntriesPlugin = require("webpack-fix-style-only-entries");
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

    config.mode = mode;

    config.entry = {
        scripts: './src/module/main.module.js',
        styles: './src/styles/styles.less',
    };

    config.output = isTest ? {} : {
        path: __dirname + '/buildbot_waterfall_view/static',
        filename: '[name].js',
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

    config.plugins = [
          new webpack.ProvidePlugin({
              "window.jQuery": "jquery",
              "$": "jquery",
          }),
        new FixStyleOnlyEntriesPlugin(),
        new MiniCssExtractPlugin({
            filename: 'styles.css',
        }),
    ];

    if (!isTest) {
        config.externals = [
            '@uirouter/angularjs',
            'angular',
            'angular-animate',
            'buildbot-data-js',
            'd3',
            'guanlecoja-ui',
            'jquery',
        ];
    }

    var cssExtractLoader = {
        loader: MiniCssExtractPlugin.loader,
        options: {
            hmr: process.env.NODE_ENV === 'development',
        },
    };

    config.module = {
        rules: [{
            test: /\.js$/,
            loader: 'babel-loader',
            exclude: /node_modules/
        }, {
            test: /\.jade$/,
            loader: 'pug-loader',
            exclude: /node_modules/
        }, {
            test: /\.css$/,
            use: [
                cssExtractLoader,
                'css-loader',
            ],
        }, {
            test: /\.less$/,
            use: [
                cssExtractLoader,
                'css-loader',
                'less-loader',
                'import-glob-loader',
            ],
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
        });

        // avoid duplicate load of angular
        config.resolve = {
            alias: {
              'angular': path.resolve(path.join(__dirname, 'node_modules', 'angular'))
            },
        };
    }

    return config;
}();
