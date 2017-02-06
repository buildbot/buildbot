# coffee script
# test goal: checks the capability to navigate in a dedicated build
# to use previous and next link


forcePage = require('./force.coffee')
builderPage = require('./builder.coffee')
waterfallPage = require('./waterfall.coffee')

describe('', () ->
    force = null
    builder = null
    waterfall = null

    beforeEach(() ->
        builder = new builderPage('runtests', 'force')
        force =  new forcePage()
        waterfall = new waterfallPage('runtests')
        builder.goDefault()
    )

    describe 'manage waterfall', () ->
        it 'should navigate to the waterfall, check one builder and hyperlink', () ->
            waterfall.go()
            waterfall.goBuilderAndCheck('runtests')

    describe 'manage waterfall build reference', () ->
        it 'should navigate to the builds waterfall and check the associated hyperlink', () ->
            waterfall.go()
            waterfall.goBuildAndCheck()

    describe 'manage waterfall build reference and popup', () ->
        it 'should navigate to the builds waterfall and open the popup and close it', () ->
            waterfall.go()
            waterfall.goBuildAndClose()
)
