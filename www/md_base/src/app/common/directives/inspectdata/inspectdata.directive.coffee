class InspectData extends Directive

    constructor: ->
        return {
            restrict: 'E'
            templateUrl: 'views/inspectdata.html'
            controller: '_InspectDataController'
            controllerAs: 'inspectdata'
            bindToController: true
            scope:
                data: '='
        }


class _InspectData extends Controller

    constructor: ->
        return if not @data
        
        @items = []

        if @data instanceof Array
            for item in @data
                @addItem item[0], item[1]
        else
            for k, v of @data
                @addItem(k, v)

    processValue: (value) ->
        if typeof(value) == 'string'
            type = 'string'
            type = 'link' if value.match /^(http|https):\/\/.+/
            return {
                type: type,
                value: value,
            }
        else if typeof(value) == 'number'
            return @processValue('' + value)
        else
            value_short = JSON.stringify(value)
            value_long = JSON.stringify(value, null, 2)
            return {
                type: 'object'
                value: value_short
                value_long: value_long
            }

    addItem: (k, v) ->
        @items.push
            key: k
            value: @processValue(v)
