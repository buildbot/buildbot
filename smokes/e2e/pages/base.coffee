# this file will contains the different generic functions which
# will be called by the different tests
# inspired by this methodology
# http://www.lindstromhenrik.com/using-protractor-with-coffeescript/


class BasePage
    # accessors for elements that all pages have have (menu, login, etc)
    constructor: () ->

    clickWhenClickable: (element) ->
        browser.wait ->
            element.click().then (->
                true
            ), ->
                element.getLocation().then (l)->
                    element.getSize().then (s)->
                        console.log 'not clickable', s, l
                false
    expectLogged: (logged) ->
        anonymousButton = element(By.cssContainingText('.dropdown', 'Anonymous'))
        expect(anonymousButton.isDisplayed()).toBe(!logged)

    logOut: ->
        element(By.css('.avatar img')).click()
        element(By.linkText('Logout')).click()
        @expectLogged(false)

    loginUser: (user, password) ->
        browser.get("http://#{user}:#{password}@localhost:8010/auth/login")
        anonymousButton = element(By.cssContainingText('.dropdown', 'Anonymous'))
        @expectLogged(true)


module.exports = BasePage
