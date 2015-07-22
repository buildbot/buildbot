class BuildTab extends Controller
    build: {}
    properties: {}
    raw_properties: {}
    number: ''

    processProperties: (data) ->
        raw = {}
        for k, v of data
            raw[k] = {value: v[0], source: v[1]} if v and v.length == 2

        @raw_properties = raw

        display = {}
        display.owners = (raw.owners.value || [])
        display.revision = (raw.got_revision.value || raw.revision.value || '')[0..10]
        display.slave = raw.slavename.value
        display.scheduler = raw.scheduler.value
        display.dir = (raw.builddir.value || raw.worddir.value)

        @properties = display

    constructor: ($scope, $state, dataService) ->
        opened = dataService.open()
        opened.closeOnDestroy($scope)

        @builderid = $state.params.builderid
        @number = $state.params.number
        opened.getBuilds(builderid:@builderid, number:@number).then (data) =>
            if data.length < 1
                alert 'No such build found'
            else
                @build = data[0]
                $scope.builder.selectTab('buildtab', @number)

                @build.loadProperties().then (data) => @processProperties(data[0])
