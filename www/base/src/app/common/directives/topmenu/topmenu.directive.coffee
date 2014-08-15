class Topmenu extends Directive('common')
    constructor: ->
        return {
            controller: '_topMenuController'
            replace: true
            restrict: 'E'
            scope: {}
            templateUrl: 'views/topmenu.html'
        }

class _topMenu extends Controller('common')
    constructor: ($scope, $element, $state) ->

        $scope.tabs = []
        select = (state) ->
            return if !state
            for tab in $scope.tabs
                if tab.name == state.data.tabid
                    tab.data.selected = true
                else
                    tab.data.selected = false
        @addTab = (tab) ->
            select(tab)
            $scope.tabs.push(tab)

        for tab in $state.get()[1...]
            if tab.data.caption?
                @addTab(tab)

        $scope.$on "$stateChangeSuccess", (ev, state) ->
            select(state)