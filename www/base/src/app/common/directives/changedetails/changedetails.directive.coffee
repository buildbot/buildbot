class Changedetails extends Directive('common')
    constructor: ->
        return {
            replace: true
            restrict: 'E'
            scope: {change: '=?'}
            templateUrl: 'views/changedetails.html'
        }
