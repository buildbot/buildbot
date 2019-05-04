// Register new module
class BBData {
    constructor() {
        return [];
    }
}

angular.module('bbData', new BBData());

const context = require.context('./', true, /^(?!.*(?:module|spec|webpack.js$)).*\.js$/);
context.keys().forEach(context);
