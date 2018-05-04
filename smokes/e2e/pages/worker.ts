// this file will contains the different generic functions which
// will be called by the different tests

import {browser, by, element, ExpectedConditions as EC} from 'protractor';
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

    async goWorker() {
        await browser.get('#/workers');
        await browser.wait(EC.urlContains('#/workers'),
                           5000,
                           "URL does not contain #/workers");
    }

    async checkWorkerPage() {
        expect(await browser.getCurrentUrl()).toContain('#/worker');
    }

    async checkHrefPresent() {
        const hrefRef = element.all(By.css('a'));
        const hrefRefText = await hrefRef.getText();
        expect(hrefRefText).toContain('slowruntests');
        expect(hrefRefText).toContain('runtests');
    }

    async goBuilderLink(builderName) {
        const builderLink = element.all(By.linkText(builderName));
        await builderLink.click();
        return new BuilderPage(builderName, 'Force');
    }
}
