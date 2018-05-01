class Changedetails
    constructor: ->
        return {
            replace: true
            restrict: 'E'
            scope:
                change: '='
                compact: '=?'
            templateUrl: 'views/changedetails.html'
        }


angular.module('common')
.directive('changedetails', [Changedetails])