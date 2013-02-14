angular.module('app').controller 'homeController', ['$log', '$scope', '$location', 'recentStorage',
    ($log, $scope, $location, recentStorage) ->
       	$scope.recent = recentStorage.get()
        # todo should get that info from data api
        $scope.config =
                bbversion: "0.9.0"
                txversion: "11.0.0"
                projectname: "cool project"
                projectversion: "0.0.1"
                projecturl: "http://buildbot.net"


]