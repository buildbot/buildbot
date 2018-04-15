/*
 * decaffeinate suggestions:
 * DS102: Remove unnecessary code created because of implicit returns
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
// this file will contains the different generic functions which
// will be called by the different tests

const BasePage = require("./base.js");

class ConsolePage extends BasePage {
    constructor() {
        {
          super();
          let thisFn = (() => { return this; }).toString();
          let thisName = thisFn.slice(thisFn.indexOf('return') + 6 + 1, thisFn.indexOf(';')).trim();
        }
    }

    go() {
        return browser.get('#/console');
    }
    countSuccess() {
        return element.all(By.css('.badge-status.results_SUCCESS')).count();
    }
}

module.exports = ConsolePage;
