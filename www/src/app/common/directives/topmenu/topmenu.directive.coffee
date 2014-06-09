angular.module('buildbot.common').directive 'topmenu',
[ ->
    controller: 'topMenuController'
    replace: true
    restrict: 'E'
    scope: {}
    templateUrl: 'views/topmenu.html'
]
