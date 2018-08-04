// Register new module
class App {
    constructor() {
        return [];
    }
}

angular.module('app', new App());

const context = require.context('./', true, /^(?!.*(?:module|spec|webpack.js$)).*\.js$/);
