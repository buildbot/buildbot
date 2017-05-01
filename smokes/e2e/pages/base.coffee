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

    logOut: ->
        element.all(By.css('.avatar img')).click()
        element.all(By.linkText('Logout')).click()
        anonymousButton = element(By.css('.dropdown'))
        expect(anonymousButton.getText()).toContain("Anonymous")

    loginUser: (user, password) ->
        browser.get("http://#{user}:#{password}@localhost:8010/auth/login")
        anonymousButton = element(By.css('.dropdown'))
        expect(anonymousButton.getText()).not.toContain("Anonymous")


module.exports = BasePage
