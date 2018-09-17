import 'angular';
import 'angular-mocks/angular-mocks';
//import uiRouter from '@uirouter/angularjs';
require("@uirouter/angularjs")
require ('../src/module/main.module.spec.js')


// app module is necessary for plugins, but only in the test environment
angular.module("app", []).constant("config", {"url": "foourl"});
