# coffee script
# test goal: checks the capability to identify the user and to start a build
# according the master.cfg file and authorization part

homePage = require('./pages/home.coffee')
forcePage = require('./pages/force.coffee')
builderPage = require('./pages/builder.coffee')

describe 'identify user as different role and check the behavior', () ->
    home = null
    force = null
    builder = null

    beforeEach () ->
        home = new homePage()
        builder = new builderPage('runtests', 'force')
        force =  new forcePage()


    afterEach () ->
        home.logOut()

    xit 'try to start a build without be identified', () ->
        errorMess = 'you need to have role \"users\"'
        builder.goForce()
        force.getStartButton().click().then () ->
            errorLoc = element.all(By.css('.alert.alert-danger'))
            expect(errorLoc.getText()).toContain(errorMess)


    it 'try to start a build as admin role', () ->
        home.loginUser("homer@email.com", "doh!")
        builder.goForce()
        force.getStartButton().click()

    xit 'try to start a build as integrators role', () ->
        errorMess = 'you need to have role \'admins\''
        home.loginUser("marge@email.com", "maggie~")
        builder.goForce()
        force.getStartButton().click().then () ->
            errorLoc = element.all(By.css('.alert.alert-danger'))
            expect(errorLoc.getText()).toContain(errorMess)
            force.getCancelButton().click()

    # xit means that the test will be deactivated
    xit 'try to start a build as users role', () ->
        errorMess = 'you need to have role \'users\''
        home.loginUser("bart@email.com", "bulldshit?")
        builder.goForce()
        force.getStartButton().click().then () ->
            errorLoc = element.all(By.css('.alert.alert-danger'))
            expect(errorLoc.getText()).toContain(errorMess)
