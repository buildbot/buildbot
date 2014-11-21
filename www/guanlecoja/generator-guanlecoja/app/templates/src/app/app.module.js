(function() {
  _.mixin(_.string.exports());

  angular.module('app', ['ui.bootstrap', 'ui.router']);

  angular.module('app').config([
    '$urlRouterProvider', function($urlRouterProvider) {
      return $urlRouterProvider.otherwise('/home');
    }
  ]);

}).call(this);
