import 'angular-animate';
import 'angular-ui-bootstrap';
import 'lodash';
import '@uirouter/angularjs';

angular.module("guanlecoja.ui", ["ui.bootstrap", "ui.router", "ngAnimate"]);

const context = require.context('./', true, /^(?!.*(?:module|spec|webpack.js$)).*\.js$/);
context.keys().forEach(context);
