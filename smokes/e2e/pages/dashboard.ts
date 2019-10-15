// this file will contains the different generic functions which
// will be called by the different tests

import { BasePage } from "./base";
import { browser, by, element, ExpectedConditions as EC } from 'protractor';

export class DashboardPage extends BasePage {
    constructor() {
        super();
    }

    async go() {
        await browser.get('#/mydashboard');
        await browser.wait(EC.urlContains('#/mydashboard'),
                           10000,
                           "URL does not contain #/mydashboard");
        var buildLink = element.all(By.linkText("runtests/1")).first();
        await browser.wait(EC.elementToBeClickable(buildLink),
                           500000,
                           "runtests/1 link not clickable");
        await buildLink.click();
    }
}
