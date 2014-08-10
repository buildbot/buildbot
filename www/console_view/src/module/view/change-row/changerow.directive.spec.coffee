beforeEach ->
    module 'console_view'
    # Mock resultsService
    module ($provide) ->
        $provide.service 'resultsService', ->
        $provide.service '$modal', ->
        null

describe 'Change row directive controller', ->
    $scope = controllerData = null

    injected = ($injector) ->
        $q = $injector.get('$q')
        $compile = $injector.get('$compile')
        $rootScope = $injector.get('$rootScope')
        $templateCache = $injector.get('$templateCache')

        # Put fake html template to templateCache
        # The other solution would be to use ngHtml2JsPreprocessor, but in this case
        # only the directive controller is tested
        $templateCache.put('buildbot.console_view/views/changerow.html', '<div></div>')

        $scope = $rootScope.$new()
        element = angular.element('<change-row change="change"></change-row>')
        $compile(element)($scope)
        $scope.$digest()
        controllerData = element.isolateScope().cr

    beforeEach(inject(injected))

    it 'should format the author and email fields correctly if it only contains an email', ->
        $scope.change =
            builds: []
            author: 'asd.oij23@ojnsdf.com'
        $scope.$digest()
        expect(controllerData.change.email).toBeDefined()
        expect(controllerData.change.email).toBe('asd.oij23@ojnsdf.com')

    it 'should format the author and email fields correctly if it contains a name and an email', ->
        $scope.change =
            builds: []
            author: 'Aksdi O. Orgei <gjfkdFj9g@fjsdb.com>'
        $scope.$digest()
        expect(controllerData.change.email).toBeDefined()
        expect(controllerData.change.author).toBe('Aksdi O. Orgei')
        expect(controllerData.change.email).toBe('gjfkdFj9g@fjsdb.com')

    it 'should not have an email field if it only contains a name', ->
        $scope.change =
            builds: []
            author: 'Okgrea Martl'
        $scope.$digest()
        expect(controllerData.change.email).toBeUndefined()
        expect(controllerData.change.author).toBe('Okgrea Martl')

    it 'should create a correct github link', ->
        $scope.change =
            builds: []
            repository: 'https://github.com/buildbot/buildbot.git'
            revision: 'a55049bc2e1320e5c4c8dba11e09079e8005668f'
        $scope.$digest()
        expect(controllerData.change.link).toBe('https://github.com/buildbot/buildbot/commit/a55049bc2e1320e5c4c8dba11e09079e8005668f')

    it 'should create correct github file links', ->
        $scope.change =
            builds: []
            repository: 'https://github.com/buildbot/buildbot.git'
            revision: 'a55049bc2e1320e5c4c8dba11e09079e8005668f'
        files = [
            'master/contrib/github_buildbot.py'
            'master/docs/developer/mq.rst'
        ]
        $scope.$digest()
        for file in files
            expect(controllerData.createFileLink(file)).toBe("https://github.com/buildbot/buildbot/blob/a55049bc2e1320e5c4c8dba11e09079e8005668f/#{file}")

    it 'should watch data changes', ->
        $scope.change =
            builds: []
        $scope.$digest()
        state1 = controllerData.change
        $scope.change =
            builds: [{}]
        $scope.$digest()
        state2 = controllerData.change
        expect(state1).not.toEqual(state2)
