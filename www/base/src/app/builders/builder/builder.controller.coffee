class Builder extends Controller
    constructor: ($rootScope, $scope, buildbotService, $stateParams, resultsService, recentStorage) ->
        # make resultsService utilities available in the template
        _.mixin($scope, resultsService)
        builder = buildbotService.one('builders', $stateParams.builder)
        builder.bind($scope).then (builder)->
            $rootScope.$broadcast "breadcrumb", [
                    caption: "Builders"
                    sref: "builders"
                ,
                    caption: builder.name
                    sref: "builder({builder:#{builder.id}})"
            ]
            recentStorage.addBuilder
                link: "#/builders/#{$scope.builder.builderid}"
                caption: $scope.builder.name
        builder.all('forceschedulers').bind($scope)
        builder.some('builds', {limit:20, order:"-number"}).bind($scope)
        builder.some('buildrequests', {claimed:0}).bind($scope)
