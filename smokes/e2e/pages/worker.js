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

const BuilderPage = require('./builder.coffee');
const BasePage = require("./base.coffee");

class WorkerPage extends BasePage {

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

    goWorker() {
        return browser.get('#/workers');
    }

    checkWorkerPage() {
        return expect(browser.getCurrentUrl()).toContain('#/worker');
    }

    checkHrefPresent() {
        const hrefRef = element.all(By.css('a'));
        expect(hrefRef.getText()).toContain('slowruntests');
        return expect(hrefRef.getText()).toContain('runtests');
    }

    goBuilderLink(builderName) {
        const builderLink = element.all(By.linkText(builderName));
        builderLink.click();
        return new BuilderPage(builderName, 'Force');
    }
}

module.exports = WorkerPage;
