# coffee script
# test goal: checks the capability to define a reason and to cancel/start the build

homePage = require('./pages/home.coffee')
forcePage = require('./pages/force.coffee')
builderPage = require('./pages/builder.coffee')

describe 'force and cancel', () ->
    force = null
    builder = null
    home = null

    beforeEach () ->
        builder = new builderPage('runtests', 'force')
        force =  new forcePage()
        home = new homePage()
        home.loginUser("homer@email.com", "doh!")

    afterEach () ->
        new homePage().waitAllBuildsFinished()
        home.logOut()

    it 'should create a build', () ->
        builder.go()
        builder.getLastSuccessBuildNumber().then (lastbuild) ->
            builder.goForce()
            force.getStartButton().click()
            builder.go()
            builder.waitNextBuildFinished(lastbuild)

    it 'should create a build with a dedicated reason and cancel it', () ->

        builder.go()
        builder.goForce()
        force.getCancelButton().click()

    it 'should create a build with a dedicated reason and Start it', () ->

        builder.go()
        builder.goForce()
        force.setReason("New Test Reason")
        force.setProjectName("BBOT9")
        force.setBranchName("Gerrit Branch")
        force.setRepo("http//name.com")
        force.setRevisionName("12345")
        force.getStartButton().click()
