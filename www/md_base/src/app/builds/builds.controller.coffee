class Builds extends Controller
    builders: []
    builderFilter: ''

    menuItems: [
        {value:'builds.masters', title: 'MASTERS', icon:'wand'}
        {value:'builds.slaves', title: 'SLAVES', icon:'hammer'}
        {value:'builds.schedulers', title: 'SCHEDULERS', icon:'clock'}
        {value:'builds.changes', title: 'LATEST CHANGES', icon:'changes'}
    ]

    isHighlighted: (name, param) ->
        return @$state.includes(name, param)

    showSideMenu: ->
        return @$mdMedia('gt-sm')

    optValue: (builder) ->
        return "builds.builder({builderid:#{builder.builderid}})"

    gotoMenuItem: (name) ->
        @$state.go(name)

    gotoBuilder: (builder) ->
        @$state.go('builds.builder', builderid: builder.builderid)

    constructor: ($scope, dataService, @$state, @$mdMedia) ->
        data = dataService.open()
        data.closeOnDestroy($scope)
        @builders = data.getBuilders().getArray()
