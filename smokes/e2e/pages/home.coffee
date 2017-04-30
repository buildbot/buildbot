# this file will contains the different generic functions which
# will be called by the different tests
# inspired by this methodology
# http://www.lindstromhenrik.com/using-protractor-with-coffeescript/

class HomePage
    #constructor: (@builder)->
    constructor: ()->

    go: () ->
        browser.get('#/')

    getPanel: () ->
        return element.all(By.css(".panel-title"))

    getAnonymousButton: ->
        anonymousButton = element(By.css('[ng-class="loginCollapsed ? \'\':\'open\'"'))
        return anonymousButton

    getLoginButton: ->
        return element(By.buttonText('Login'))

    setUserText: (value) ->
        setUserValue = element.all(By.css('[ng-model="username"]'))
        setUserValue.clear()
        setUserValue.sendKeys(value)

    setPasswordText: (value) ->
        setPasswordValue = element.all(By.css('[ng-model="password"]'))
        setPasswordValue.clear()
        setPasswordValue.sendKeys(value)

    logOut: ->
        @go()
        element.all(By.css('.avatar img')).click()
        element.all(By.linkText('Logout')).click()
        anonymousButton = element(By.css('.dropdown'))
        expect(anonymousButton.getText()).toContain("Anonymous")

    loginUser: (user, password) ->
        browser.get("http://#{user}:#{password}@localhost:8010/auth/login")
        anonymousButton = element(By.css('.dropdown'))
        expect(anonymousButton.getText()).not.toContain("Anonymous")

    waitAllBuildsFinished: () ->
        @go()
        self = this
        noRunningBuilds = () ->
            element.all(By.css("h4")).getText().then (text) ->
                text = text.join(" ")
                return text.toLowerCase().indexOf("0 build running") >= 0
        browser.wait(noRunningBuilds, 20000)

module.exports = HomePage
