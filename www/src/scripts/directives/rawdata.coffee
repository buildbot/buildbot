angular.module('app').directive 'rawdata',
['$log', ($log) ->
    replace: true
    restrict: 'E'
    scope: {data:'='}
    templateUrl: 'views/directives/rawdata.html'
]
