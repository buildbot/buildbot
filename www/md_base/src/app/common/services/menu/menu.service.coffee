class Menu extends Provider
    items: []
    current: ''

    addItem: (item) ->
        item.order ?= 99
        @items.push item

    $get: [
        '$rootScope',
        ($rootScope) ->
            $rootScope.$on '$stateChangeSuccess', (event, toState) =>
                @current = toState.name

            return {
                getItems: => @items
                getCurrent: => @current
            }
    ]


class GlMenu extends Provider
    # a proxy provider to provide compatibility to older plugins

    constructor: (@menuServiceProvider) ->

    addGroup: (group) ->
        # proxy addGroup to addItem.
        # nested items will be supported no longer
        
        @menuServiceProvider.addItem group

    $get: ->
        # this method should never be used
        # but we will return the same result of menuServiceProvider

        return @menuServiceProvider.$get()
