// this file will contains the different generic functions which
// will be called by the different tests

const BasePage = require("./base.js");

class HomePage extends BasePage {

    constructor(){
        {
          super();
          let thisFn = (() => { return this; }).toString();
          let thisName = thisFn.slice(thisFn.indexOf('return') + 6 + 1, thisFn.indexOf(';')).trim();
        }
    }

    go() {
        return browser.get('#/');
    }

    getPanel() {
        return element.all(By.css(".panel-title"));
    }

    getAnonymousButton() {
        const anonymousButton = element(By.css('[ng-class="loginCollapsed ? \'\':\'open\'"'));
        return anonymousButton;
    }

    getLoginButton() {
        return element(By.buttonText('Login'));
    }

    setUserText(value) {
        const setUserValue = element.all(By.css('[ng-model="username"]'));
        setUserValue.clear();
        return setUserValue.sendKeys(value);
    }

    setPasswordText(value) {
        const setPasswordValue = element.all(By.css('[ng-model="password"]'));
        setPasswordValue.clear();
        return setPasswordValue.sendKeys(value);
    }

    waitAllBuildsFinished() {
        this.go();
        const self = this;
        const noRunningBuilds = () =>
            element.all(By.css("h4")).getText().then(function(text) {
                text = text.join(" ");
                return text.toLowerCase().indexOf("0 builds running") >= 0;
            })
        ;
        return browser.wait(noRunningBuilds, 20000);
    }
}

module.exports = HomePage;
