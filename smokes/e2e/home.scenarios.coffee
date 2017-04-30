# coffee script
# test goal: checks the the number of element present in home page
# to test this part: two different builds need to be started

forcePage = require('./pages/force.coffee')
builderPage = require('./pages/builder.coffee')
homePage = require('./pages/home.coffee')

describe 'home page', () ->
    force = null
    builder = null
    home = null

    beforeEach () ->
        builder = new builderPage('runtests', 'force')
        force =  new forcePage()
        home = new homePage()
        home.loginUser("my@email.com", "mypass")

    afterEach () ->
        home.logOut()

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
