# base widget handling has-error, and error message popups
angular.module('app').directive 'basefield',
['$log', ($log) ->
    replace: true
    transclude: true
    restrict: 'E'
    scope: true
    templateUrl: "views/basefield.html"
    controller: [ "$scope", ($scope) ->
        # clear error on value change
        $scope.$watch "field.value", (o,n) ->
            $scope.field.errors = ""
    ]
]
