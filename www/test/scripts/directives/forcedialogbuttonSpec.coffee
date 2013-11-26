if window.__karma__?
    beforeEach(module 'devapp')

    pureStubs = {}
    stubs = {}
    spies = {}
    afterEach ->
        angular.forEach(stubs, (stub) ->
            stub.restore()
        )
        angular.forEach(spies, (spy) ->
            spy.reset()
        )

    describe 'force dialog button directive', ->

        elem = {}
        buildbotService = {}
        $compile = {}
        $scope = {}
        $modal = {}
        $document = {}
        $httpBackend = {}
        $rootScope = {}

        afterEach ->
            body = $document.find('body')
            body.find('div.modal').remove()
            body.find('div.modal-backdrop').remove()
            $httpBackend.resetExpectations()

        injected = ($injector) ->

            $window = $injector.get('$window')
            $templateCache = $injector.get('$templateCache')
            directivePath = 'views/directives/'

            forceDialogTpl =  directivePath + 'forcedialog.html'
            nestedFieldTpl = directivePath + 'nestedfield.html'

            #TODO: use ng-html2js instead..w/ ng-html2js should be able to use w/ beforeEach module 'path/to/tpl'
            $templateCache.put(forceDialogTpl, window.__html__['buildbot_www/' + forceDialogTpl])
            $templateCache.put(nestedFieldTpl, window.__html__['buildbot_www/' + nestedFieldTpl])

            $httpBackend = $injector.get('$httpBackend')
            $document = $injector.get('$document')
            $modal = $injector.get('$modal')
            spies.openModal = sinon.spy($modal, 'open')

            $rootScope = $injector.get('$rootScope')
            $scope = $rootScope.$new()

            buildbotService = $injector.get('buildbotService')

            $compile = $injector.get('$compile')
            stubs.bbServiceAll = sinon.stub(buildbotService, "all")
            pureStubs.getListStub = sinon.stub()
            pureStubs.thenStub = sinon.stub()
            pureStubs.thenStub.callsArgWith(0, [
                {
                    name : "someScheduler",
                    "all_fields" : [{
                        "columns":1,
                        "css_class":"",
                        "debug":true,
                        "default":"",
                        "fields": [
                            {
                                "columns":1,
                                "css_class":"",
                                "debug":true,
                                "default":"",
                                "fields":[
                                    {
                                        "css_class":"",
                                        "debug":true,
                                        "default":"",
                                        "fullName":"username",
                                        "hide":false,
                                        "label":"Your name:",
                                        "multiple":false,
                                        "name":"username",
                                        "need_email":true,
                                        "parentName":null,
                                        "regex":null,
                                        "required":false,
                                        "size":30,
                                        "subtype":"",
                                        "type":"text"
                                    },
                                    {
                                        "css_class":"",
                                        "debug":true,
                                        "default":"force build",
                                        "fullName":"reason",
                                        "hide":false,
                                        "label":"reason",
                                        "multiple":false,
                                        "name":"reason",
                                        "parentName":null,
                                        "regex":null,
                                        "required":false,
                                        "size":20,
                                        "subtype":"",
                                        "type":"text"
                                    }
                                ],
                                "fullName":null,
                                "hide":false,
                                "label":"",
                                "multiple":false,
                                "name":"",
                                "parentName":null,
                                "regex":null,
                                "required":false,
                                "subtype":"",
                                "type":"nested"
                            },
                            {
                                "columns":2,
                                "css_class":"",
                                "debug":true,
                                "default":"",
                                "fields":[
                                    {
                                        "columns":1,
                                        "css_class":"",
                                        "debug":true,
                                        "default":"",
                                        "fields":[
                                            {
                                                "css_class":"",
                                                "debug":true,
                                                "default":"",
                                                "fullName":"property1_name",
                                                "hide":false,
                                                "label":"Name:",
                                                "multiple":false,
                                                "name":"name",
                                                "parentName":"property1",
                                                "regex":null,
                                                "required":false,
                                                "size":10,
                                                "subtype":"",
                                                "type":"text"
                                            },
                                            {
                                                "css_class":"",
                                                "debug":true,
                                                "default":"",
                                                "fullName":"property1_value",
                                                "hide":false,
                                                "label":"Value:",
                                                "multiple":false,
                                                "name":"value",
                                                "parentName":"property1",
                                                "regex":null,
                                                "required":false,
                                                "size":10,
                                                "subtype":"",
                                                "type":"text"
                                            }
                                        ],
                                        "fullName":"property1",
                                        "hide":false,
                                        "label":"",
                                        "multiple":false,
                                        "name":"property1",
                                        "parentName":null,
                                        "regex":null,
                                        "required":false,
                                        "subtype":"any",
                                        "type":"nested"
                                    },
                                    {
                                        "columns":1,
                                        "css_class":"",
                                        "debug":true,
                                        "default":"",
                                        "fields":[
                                            {
                                                "css_class":"",
                                                "debug":true,
                                                "default":"",
                                                "fullName":"property2_name",
                                                "hide":false,
                                                "label":"Name:",
                                                "multiple":false,
                                                "name":"name",
                                                "parentName":"property2",
                                                "regex":null,
                                                "required":false,
                                                "size":10,
                                                "subtype":"",
                                                "type":"text"
                                            },
                                            {
                                                "css_class":"",
                                                "debug":true,
                                                "default":"",
                                                "fullName":"property2_value",
                                                "hide":false,
                                                "label":"Value:",
                                                "multiple":false,
                                                "name":"value",
                                                "parentName":"property2",
                                                "regex":null,
                                                "required":false,
                                                "size":10,
                                                "subtype":"",
                                                "type":"text"
                                            }
                                        ],
                                        "fullName":"property2",
                                        "hide":false,
                                        "label":"",
                                        "multiple":false,
                                        "name":"property2",
                                        "parentName":null,
                                        "regex":null,
                                        "required":false,
                                        "subtype":"any",
                                        "type":"nested"
                                    }
                                ],
                                "fullName":null,
                                "hide":false,
                                "label":"",
                                "multiple":false,
                                "name":"",
                                "parentName":null,
                                "regex":null,
                                "required":false,
                                "subtype":"",
                                "type":"nested"
                            }
                        ]
                    }
                    ]

                },
                {
                    name : "anotherScheduler.."
                }
            ])
            pureStubs.getListStub.returns({
                then : pureStubs.thenStub
            })
            stubs.bbServiceAll.returns({
                getList : pureStubs.getListStub
            })


        beforeEach(inject(injected))

        beforeEach ->
            this.addMatchers({
                toHaveModalsOpen: (noOfModals) ->
                    modalDomEls = this.actual.find('body > div.modal')
                    return modalDomEls.length == noOfModals
                toHaveModalWithTitle: (title) ->
                    return this.actual.find('.modal-header > h4').text() == title

            })


        beforeEach( ->
            $scope.scheduler = {
                "name" : "someScheduler"
            }

            markup = '<forcedialogbutton class=".btn .btn-default" scheduler="{{scheduler.name}}">{{scheduler.name}}</forcedialogbutton>'

            elem = $compile(markup)($scope)
            $scope.$apply()

        )

        describe 'when the button is clicked', ->

            beforeEach ->
                elem.click()
                $scope.$digest()

            it 'should create a new modal', ->
                expect($modal.open.called).toBe(true)

            it 'should have opened a new model DOM element', ->
                expect($document).toHaveModalsOpen(1)

            it 'should open a modal with the expected title', ->

                #have to do this since a new scope is created for the modal..
                $rootScope.$digest()

                expect($document).toHaveModalWithTitle($scope.scheduler.name)

            describe 'when the modal cancel button is clicked', ->

                beforeEach ->
                    $document.find('.modal-footer > button')[0].click()
                    $scope.$digest()

                it 'should remove the modal', ->
                    expect($document).toHaveModalsOpen(0)




















