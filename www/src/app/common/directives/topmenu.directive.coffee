angular.module('app').directive 'topmenu',
['$log', ($log) ->
    controller = [
        '$scope', '$element', 'topMenuStates', ($scope, $element, topMenuStates) ->

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

            for tab in topMenuStates
                if tab.data.caption?
                    @addTab(tab)

            $scope.$on "$stateChangeSuccess", (ev, state) ->
                select(state)
        ]
    controller: controller
    replace: true
    restrict: 'E'
    scope: {}
    templateUrl: 'views/topmenu.html'
]
