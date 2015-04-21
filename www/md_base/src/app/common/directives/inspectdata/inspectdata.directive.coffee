class InspectData extends Directive

    constructor: ->
        return {
            restrict: 'E'
            templateUrl: 'views/inspectdata.html'
            controller: '_InspectDataController'
            controllerAs: 'inspectdata'
            scope:
                data: '='
        }


class _InspectData extends Controller
    addItem: (k, v) ->
        v = JSON.stringify(v) if typeof(v) != 'string'
        @items.push
            key: k
            value: v

    constructor: ($scope) ->
        return if not $scope.data
        
        @items = []
        @data = $scope.data

        if @data instanceof Array
            for item in @data
                @addItem item[0], item[1]
        else
            for k, v of @data
                @addItem(k, v)


