angular.module('app').controller 'homeController',
['$log', '$scope', '$location', 'recentStorage'
    ($log, $scope, $location, recentStorage) ->
        $scope.recent = recentStorage.get()
]
