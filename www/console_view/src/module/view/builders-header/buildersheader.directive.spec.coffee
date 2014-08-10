beforeEach ->
    # Mocked dependency
    module 'console_view'

describe 'Builders header directive controller', ->
    $scope = controllerData = null

    injected = ($injector) ->
        $q = $injector.get('$q')
        $compile = $injector.get('$compile')
        $rootScope = $injector.get('$rootScope')
        $templateCache = $injector.get('$templateCache')

        # Put fake html template to templateCache
        # The other solution would be to use ngHtml2JsPreprocessor, but in this case
        # only the directive controller is tested
        $templateCache.put('console_view/views/buildersheader.html', '<div></div>')

        $scope = $rootScope.$new()
        element = angular.element('<builders-header builders="builders"></builders-header>')
        $compile(element)($scope)
        $scope.$digest()
        controllerData = element.isolateScope().bh

    beforeEach(inject(injected))

    it 'should watch data changes', ->
        $scope.builders = [{}]
        $scope.$digest()
        builders1 = controllerData.builders
        $scope.builders = [{}, {}]
        $scope.$digest()
        builders2 = controllerData.builders
        expect(builders1).not.toEqual(builders2)
