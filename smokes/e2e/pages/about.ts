// this file will contains the different generic functions which
// will be called by the different tests

import { BasePage } from "./base";
import { browser, by, element, ExpectedConditions as EC } from 'protractor';

export class AboutPage extends BasePage {
    constructor(builder) {
        super();
        this.builder = builder;
    }

    async goAbout() {
        await browser.get('#/about');
        await browser.wait(EC.urlContains('#/about'),
                           10000,
                           "URL does not contain #/about");
    }

    async checkBuildbotTitle() {
        const aboutTitle = element.all(By.css('h2')).first();
        const title:string = await aboutTitle.getText();
        expect(title).toContain('About this');
        expect(title).toContain('buildbot');
    }

    async checkConfigTitle() {
        const configurationTitle = element.all(By.css('h2')).get(1);
        const title:string = await configurationTitle.getText();
        expect(title).toContain('Configuration');
    }

    async checkAPIDescriptionTitle() {
        const dependenciesTitle = element.all(By.css('h2')).get(2);
        const dependenciesText:string = await dependenciesTitle.getText();
        expect(dependenciesText).toContain('API description');
    }
}
