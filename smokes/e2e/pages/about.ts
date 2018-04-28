// this file will contains the different generic functions which
// will be called by the different tests

import { BasePage } from "./base";

export class AboutPage extends BasePage {
    constructor(builder) {
        {
          super();
          let thisFn = (() => { return this; }).toString();
          let thisName = thisFn.slice(thisFn.indexOf('return') + 6 + 1, thisFn.indexOf(';')).trim();
        }
        this.builder = builder;
    }

    goAbout() {
        return browser.get('#/about');
    }

    checkAboutPage() {
        expect(browser.getCurrentUrl()).toContain('#/about');
    }

    checkBuildbotTitle() {
        const aboutTitle = element.all(By.css('h2')).first();
        expect(aboutTitle.getText()).toContain('About this');
        expect(aboutTitle.getText()).toContain('buildbot');
    }

    checkConfigTitle() {
        const configurationTitle = element.all(By.css('h2')).get(1);
        expect(configurationTitle.getText()).toContain('Configuration');
    }

    checkDependenciesTitle() {
        const dependenciesTitle = element.all(By.css('h2')).get(2);
        expect(dependenciesTitle.getText()).toContain('Javascript dependencies');
    }
}
