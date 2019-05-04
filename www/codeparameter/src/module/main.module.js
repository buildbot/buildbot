
angular.module("codeparameter", ['ui.ace', 'common']);

const context = require.context('./', true, /^(?!.*(?:module|spec|webpack.js$)).*\.js$/);
context.keys().forEach(context);
