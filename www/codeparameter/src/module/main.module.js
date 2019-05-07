
import 'ace-builds/src-noconflict/ace';
import "ace-builds/webpack-resolver";
import 'angular-ui-ace';

angular.module("codeparameter", ['ui.ace', 'common']);

require('./codefield.directive.js');
