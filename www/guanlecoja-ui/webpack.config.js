'use strict';

// Modules
var webpack = require('webpack');
const env = require('yargs').argv.env;
var autoprefixer = require('autoprefixer');
var HtmlWebpackPlugin = require('html-webpack-plugin');
var ExtractTextPlugin = require('extract-text-webpack-plugin');
var CopyWebpackPlugin = require('copy-webpack-plugin');
const MiniCssExtractPlugin = require('mini-css-extract-plugin');
const FixStyleOnlyEntriesPlugin = require("webpack-fix-style-only-entries");
const pkg = require('./package.json');

let libraryName = pkg.name;

var event = process.env.npm_lifecycle_event;

var isTest = event === 'test' || event === 'test-watch';
var isProd = env === 'prod';

let outputFile, mode;

if (isProd) {
    mode = 'production';
    outputFile = libraryName + '.min';
} else {
    mode = 'development';
    outputFile = libraryName;
}

module.exports = function makeWebpackConfig() {

    var config = {};

    config.mode = mode;

    config.entry = {
        styles: './src/styles/styles.less',
        [outputFile]: './src/module/main.module.js'
    };

    config.output = isTest ? {} : {
        path: __dirname + '/dist',
        filename: '[name].js',
        library: libraryName,
        libraryTarget: 'umd',
        umdNamedDefine: true,
        globalObject: "typeof self !== 'undefined' ? self : this",
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

    if (!isTest) {
        config.externals = [
            'angular',
            '@uirouter/angularjs',
            'angular-animate',
            'angular-ui-bootstrap',
            'jquery',
            'lodash',
        ];
    }

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
