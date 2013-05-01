beforeEach module 'app'

beforeEach ->
    this.addMatchers { toEqualData: (expected) ->
        angular.equals this.actual, expected }

describe 'buildbot service', ->
    buildbotService = {}
    $httpBackend = {}
    $scope = {}
    beforeEach inject (_$httpBackend_, $injector) ->
        $httpBackend = _$httpBackend_
        $httpBackend.expectGET('api/v2/changes')
        .respond []
        buildbotService = $injector.get('buildbotService')

    it 'should query for changes at /changes and receive an array', ->

        buildbotService.populateScope $scope, "changes", "changes", "changes"
        # $httpBackend.flush()