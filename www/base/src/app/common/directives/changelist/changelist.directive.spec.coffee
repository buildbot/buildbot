beforeEach module 'app'

describe 'changelist controller', ->
    $scope = $rootScope = createController = null

    injected = ($injector) ->
        $rootScope = $injector.get('$rootScope')
        $scope = $rootScope.$new()
        $controller = $injector.get('$controller')
        createController = ->
            return $controller '_changeListController',
                '$scope': $scope

    beforeEach(inject(injected))

    it 'should calculate authors emails', ->
        controller = createController()
        $scope.changes = [
            author: "foo <bar@foo.com>"
        ,
            author: "bar <foo@foo.com>"
        ]
        $scope.$digest()
        expect($scope.changes[0].author_email).toBe("bar@foo.com")
        expect($scope.changes[1].author_email).toBe("foo@foo.com")
