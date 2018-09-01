// this file will contains the different generic functions which
// will be called by the different tests
// inspired by this methodology
// http://www.lindstromhenrik.com/using-protractor-with.jsscript/


export class BasePage {
    // accessors for elements that all pages have have (menu, login, etc)
    constructor() {}

    async logOut() {
        await element(By.css('.avatar img')).click();
        await element(By.linkText('Logout')).click();
        const anonymousButton = element(By.css('.dropdown'));
        expect(await anonymousButton.getText()).toContain("Anonymous");
    }

    async loginUser(user, password) {
        await browser.get(`http://${user}:${password}@localhost:8010/auth/login`);
        const anonymousButton = element(By.css('.dropdown'));
        expect(await anonymousButton.getText()).not.toContain("Anonymous");
    }
}
