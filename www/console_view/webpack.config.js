

var path = require('path');
const ExtractTextPlugin = require("extract-text-webpack-plugin");

const extractLess = new ExtractTextPlugin({
    filename: "styles.css",
});

pluginName = "console_view"
pluginPythonName = "buildbot_console_view"

function isExternal(module) {
  var context = module.context;

  if (typeof context !== 'string') {
    return false;
  }

  return context.indexOf('node_modules') !== -1;
}

module.exports = {

    entry: {
        scripts: "./src/module/main.module.js",
        styles: "./src/styles/styles.less",
        tests: "./src/module/main.module.spec.js",
    },
    output: {
        path: path.resolve(__dirname, "./"+pluginPythonName+"/static"),
        filename: "[name].js"
    },
    plugins: [
        extractLess
    ],

    // Enable sourcemaps for debugging webpack's output.
    devtool: "source-map",

    resolve: {
        extensions: [".js", ".json"],
    },

    module: {
        rules: [
            {
                  // Transpile .js files using babel-loader
                  // Compiles ES6 and ES7 into ES5 code
                  test: /\.js$/,
                  loader: 'babel-loader',
                  exclude: /node_modules/
            },
            // All files with a '.ts' or '.tsx' extension will be handled by 'ts-loader' or awesome-typescript-loader'.
            { test: /\.tsx?$/, loader: "awesome-typescript-loader" },

            // All output '.js' files will have any sourcemaps re-processed by 'source-map-loader'.
            { 
                enforce: "pre", 
                test: /\.js$/, 
                loader: "source-map-loader",
            },
            {
                test: /\.css$/,
                loader: ExtractTextPlugin.extract("style-loader", "css-loader")
            },
            {
                test: /\.less$/,
                use: extractLess.extract({
                use: [{
                    loader: "css-loader"
                }, {
                    loader: "less-loader"
                }],
                // use style-loader in development
                fallback: "style-loader"
                })
            },
            {
                test: /\.coffee$/,
                use: [ 'coffee-loader', 'ng-classify-loader' ]
            },
            { test: /\.jade$/, loader: 'raw-loader!jade-html-loader' },

        ],
    },
};