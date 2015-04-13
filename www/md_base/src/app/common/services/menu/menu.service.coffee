class Menu extends Provider
    title_icon: 'menu'
    items: []
    current: ''

    addItem: (item) ->
        item.order ?= 99
        @items.push item

    $get: ($rootScope) ->
        $rootScope.$on '$stateChangeSuccess', (event, toState) =>
            @current = toState.name

        return {
            getItems: => @items
            getCurrent: => @current
        }
