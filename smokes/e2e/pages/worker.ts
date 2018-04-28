// this file will contains the different generic functions which
// will be called by the different tests

import { BuilderPage } from './builder';
import { BasePage } from "./base";

export class WorkerPage extends BasePage {

    constructor(builder) {
        {
          super();
          let thisFn = (() => { return this; }).toString();
          let thisName = thisFn.slice(thisFn.indexOf('return') + 6 + 1, thisFn.indexOf(';')).trim();
        }
        this.builder = builder;
    }

    goWorker() {
        return browser.get('#/workers');
    }

    checkWorkerPage() {
        expect(browser.getCurrentUrl()).toContain('#/worker');
    }

    checkHrefPresent() {
        const hrefRef = element.all(By.css('a'));
        expect(hrefRef.getText()).toContain('slowruntests');
        expect(hrefRef.getText()).toContain('runtests');
    }

    goBuilderLink(builderName) {
        const builderLink = element.all(By.linkText(builderName));
        builderLink.click();
        return new BuilderPage(builderName, 'Force');
    }
}
