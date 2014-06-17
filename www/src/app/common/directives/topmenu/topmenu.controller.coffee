angular.module('buildbot.common').controller 'topMenuController',
    ['$scope', '$element', '$state', ($scope, $element, $state) ->

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
    ]