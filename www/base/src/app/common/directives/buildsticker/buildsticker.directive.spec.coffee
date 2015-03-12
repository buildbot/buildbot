beforeEach module 'app'

describe 'buildsticker controller', ->
    buildbotService = mqService = $httpBackend = $rootScope = $compile = null

    injected = ($injector) ->
        $compile = $injector.get('$compile')
        $httpBackend = $injector.get('$httpBackend')
        $location = $injector.get('$location')
        decorateHttpBackend($httpBackend)
        $rootScope = $injector.get('$rootScope')
        mqService = $injector.get('mqService')
        $controller = $injector.get('$controller')
        $q = $injector.get('$q')

        # stub out the actual backend of mqservice
        spyOn(mqService,"setBaseUrl").and.returnValue(null)
        spyOn(mqService,"startConsuming").and.returnValue($q.when( -> ))
        spyOn(mqService,"stopConsuming").and.returnValue(null)
        buildbotService = $injector.get('buildbotService')

    beforeEach(inject(injected))

    afterEach ->
        $httpBackend.verifyNoOutstandingExpectation()
        $httpBackend.verifyNoOutstandingRequest()

    it 'directive should generate correct html', ->
        $httpBackend.expectDataGET('builds/1')
        buildbotService.one('builds', 1).bind($rootScope)
        $httpBackend.flush()
        $httpBackend.expectDataGET('builders/1')
        element = $compile("<buildsticker build='build'></buildsticker>")($rootScope)
        $httpBackend.flush()
        $rootScope.build.started_at = moment.unix() # avoid test failed due to time changes
        $rootScope.$digest()
        html = element.html()

        expectHtml = '''
        <div class="panel-heading no-select">
            <div class="row">
                <span ng-class="results2class(build)" class="pull-right label ng-binding results_WARNINGS">WARNINGS</span>
                <a ui-sref="build({builder:builder.builderid, build:build.number})" class="ng-binding" href="#/builders/2/builds/1">11/1</a>
            </div>
            <div class="row">
                <span ng-show="build.complete" class="pull-right ng-binding ng-hide">0 s</span>
                <span ng-show="!build.complete" class="pull-right ng-binding">0 s</span>
                <span class="ng-binding">mystate_string</span>
            </div>
        </div>
        '''
        expectHtml = (s.trim() for s in expectHtml.split('\n')).join('')

        expect(html).toBe(expectHtml)
