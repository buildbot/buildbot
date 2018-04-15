/*
 * decaffeinate suggestions:
 * DS001: Remove Babel/TypeScript constructor workaround
 * DS102: Remove unnecessary code created because of implicit returns
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
// this file will contains the different generic functions which
// will be called by the different tests
// inspired by this methodology
// http://www.lindstromhenrik.com/using-protractor-with-coffeescript/

const BasePage = require("./base.coffee");

class AboutPage extends BasePage {
    constructor(builder) {
        {
          // Hack: trick Babel/TypeScript into allowing this before super.
          if (false) { super(); }
          let thisFn = (() => { return this; }).toString();
          let thisName = thisFn.slice(thisFn.indexOf('return') + 6 + 1, thisFn.indexOf(';')).trim();
          eval(`${thisName} = this;`);
        }
        this.builder = builder;
    }

    goAbout() {
        return browser.get('#/about');
    }

    checkAboutPage() {
        return expect(browser.getCurrentUrl()).toContain('#/about');
    }

    checkBuildbotTitle() {
        const aboutTitle = element.all(By.css('h2')).first();
        expect(aboutTitle.getText()).toContain('About this');
        return expect(aboutTitle.getText()).toContain('buildbot');
    }

    checkConfigTitle() {
        const configurationTitle = element.all(By.css('h2')).get(1);
        return expect(configurationTitle.getText()).toContain('Configuration');
    }

    checkDependenciesTitle() {
        const dependenciesTitle = element.all(By.css('h2')).get(2);
        return expect(dependenciesTitle.getText()).toContain('Javascript dependencies');
    }
}

module.exports = AboutPage;
