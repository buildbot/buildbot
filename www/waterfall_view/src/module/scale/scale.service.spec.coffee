beforeEach ->
    module 'waterfall_view'

describe 'Scale service', ->

    ###
    # Test data
    ###
    builders = [
        builderid: 1
        name: 'builder1'
    ,
        builderid: 2
        name: 'builder2'
    ,
        builderid: 3
        name: 'builder3'
    ,
        builderid: 4
        name: 'builder4'
    ]

    builds = [
        buildid: 1
        builderid: 1
        started_at: 1403059709
        complete_at: 1403059772
        complete: true
    ,
        buildid: 2
        builderid: 2
        buildrequestid: 1
        started_at: 1403059711
        complete_at: 1403060287
        complete: true
    ,
        buildid: 3
        builderid: 4
        buildrequestid: 2
        started_at: 1403059710
        complete_at: 1403060278
        complete: true
    ,
        buildid: 4
        builderid: 3
        buildrequestid: 2
        started_at: 1403059710
        complete_at: 0
        complete: false
    ]

    scaleService = null

    injected = ($injector) ->
        $rootScope = $injector.get('$rootScope')
        d3Service = $injector.get('d3Service')
        scaleService = $injector.get('scaleService')

    beforeEach(inject(injected))

    it 'should be defined', ->
        expect(scaleService).toBeDefined()

    it 'should return a builderid to name scale', ->
        console.log scaleService