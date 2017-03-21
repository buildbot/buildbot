beforeEach ->
    module 'console_view'
    # Mock resultsService
    module ($provide) ->
        $provide.service 'resultsService', ->
        $provide.service '$uibModal', ->
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
