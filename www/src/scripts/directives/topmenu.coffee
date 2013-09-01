angular.module('app').directive 'topmenu',
['$log', 'route_config', ($log, route_config) ->
    controller = [
        '$scope', '$element', '$rootScope', ($scope, $element, $rootScope) ->
            $scope.tabs = []
            $scope.select = (tab) ->
                return if tab.selected is true
                angular.forEach $scope.tabs, (tab) ->
                    tab.selected = false

                tab.selected = true

            @addTab = (tab, tabId) ->
                $scope.select tab if $scope.tabs.length is 0
                $scope.tabs.push tab

            for id, tab of route_config
                if tab.caption?
                    @addTab(tab, id)

            $rootScope.$watch("selectedTab", $scope.select)
        ]
    controller: controller
    replace: true
    restrict: 'E'
    scope: {}
    templateUrl: 'views/directives/topmenu.html'
]
