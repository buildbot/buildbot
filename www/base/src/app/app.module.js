class App {
    constructor() { return [
        'buildbot_config',
        'ngAnimate',
        'ui.bootstrap',
        'ui.router',
        'RecursionHelper',
        'guanlecoja.ui',
        'bbData',
        'btorfs.multiselect'
    ]; }
}


angular.module('app', new App());

const context = require.context('./', true, /\.spec.js$/);
context.keys().forEach(context);
