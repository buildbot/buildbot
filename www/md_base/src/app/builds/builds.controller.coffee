class Builds extends Controller
    builders: []
    builderFilter: ''

    selectOptions: [
        {value:'builds.masters', title: 'MASTERS'}
        {value:'builds.slaves', title: 'SLAVES'}
        {value:'builds.schedulers', title: 'SCHEDULERS'}
        {value:'builds.changes', title: 'LATEST CHANGES'}
    ]
    selectedOption: ''
    builderOptionValue: 'builds.builder'

    isHighlighted: (name, param) ->
        return @$state.is(name, param)

    showMenu: ->
        return @$mdMedia('gt-sm')

    constructor: ($scope, dataService, @$state, @$mdMedia) ->
        opened = dataService.open()
        opened.closeOnDestroy($scope)
        @builders = opened.getBuilders().getArray()
        @selectedOption = @$state.$current.name
