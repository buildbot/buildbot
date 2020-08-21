// this file will contains the different generic functions which
// will be called by the different tests

import { BuilderPage } from './builder';
import { BasePage } from "./base";
import { browser, by, element, ExpectedConditions as EC } from 'protractor';
import { bbrowser } from '../utils';

export class WorkerPage extends BasePage {
    builder: string;

    constructor(builder) {
        super();
        this.builder = builder;
    }

    async goWorker() {
        await bbrowser.get('#/workers');
        await bbrowser.wait(EC.urlContains('#/workers'),
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
        let builderLink = element(By.linkText(builderName));
        await bbrowser.wait(EC.elementToBeClickable(builderLink),
                            "link for " + builderName + " not clickable");
        await builderLink.click();
        return new BuilderPage(builderName, 'Force');
    }
}
