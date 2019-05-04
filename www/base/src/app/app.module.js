import '@uirouter/angularjs';
import 'angular-animate';
import 'angular-bootstrap-multiselect';
import 'angular-recursion';
import 'angular-ui-bootstrap';
import 'guanlecoja-ui';
import 'buildbot-data-js';

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

require('./common/common.module.js');

const context = require.context('./', true, /^(?!.*(?:module|spec|webpack.js$)).*\.js$/);
context.keys().forEach(context);
