class Changedetails extends Directive('common')
    constructor: ->
        return {
            replace: true
            restrict: 'E'
            scope:
                change: '='
                compact: '=?'
            templateUrl: 'views/changedetails.html'
        }
