// this file will contains the different generic functions which
// will be called by the different tests
// inspired by this methodology
// http://www.lindstromhenrik.com/using-protractor-with.jsscript/

import { bbrowser } from '../utils';

export const testPageUrl = 'http://localhost:8011'

export class BasePage {
    // accessors for elements that all pages have (menu, login, etc)
    constructor() {}

    async logOut() {
        await element(By.css('.navbar-right a.dropdown-toggle')).click();
        await element(By.linkText('Logout')).click();
        const anonymousButton = element.all(By.css('.dropdown')).first();
        expect(await anonymousButton.getText()).toContain("Anonymous");
    }

    async loginUser(user, password) {
        await bbrowser.get(`http://${user}:${password}@localhost:8011/auth/login`);
        const anonymousButton = element.all(By.css('.dropdown')).first();
        expect(await anonymousButton.getText()).not.toContain("Anonymous");
    }
}
