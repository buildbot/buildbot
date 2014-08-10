class Builders extends Controller
    constructor: ($scope, buildbotService, resultsService) ->
        # make resultsService utilities available in the template
        _.mixin($scope, resultsService)

        buildbotService.all('builders').bind $scope,
            onchild: (builder) ->
                builder.all('buildslaves').bind $scope,
                    dest: builder
                builder.some('builds', {limit:20, order:"-number"}).bind $scope,
                    dest: builder