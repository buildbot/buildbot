# coffee script
# test goal: checks the the number of element present in home page
# to test this part: two different builds need to be started


forcePage = require('./force.coffee')
builderPage = require('./builder.coffee')
homePage = require('./home.coffee')


describe('', () ->
    force = null
    builder = null
    home = null

    beforeEach(() ->
        builder = new builderPage('runtests', 'force')
        force =  new forcePage()
        home = new homePage()
        builder.goDefault()
    )

    describe 'manage home web page', () ->
        it 'should go to the home page and check the different builder', () ->
            builderName = {
                "0" : "runtests"
            }
            builder.go()
            builder.goForce()
            force.getStartButton().click()
            home.go()
            panel0 = home.getPanel(0)
            expect(panel0.getText()).toContain(builderName[0])
)
