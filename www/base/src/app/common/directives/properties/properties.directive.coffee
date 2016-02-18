class Properties extends Directive('common')
    constructor: ->
        return {
            replace: true
            restrict: 'E'
            scope: {properties: '='}
            templateUrl: 'views/properties.html'
        }
