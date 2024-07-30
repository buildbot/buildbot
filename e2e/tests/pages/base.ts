/*
  This file is part of Buildbot.  Buildbot is free software: you can
  redistribute it and/or modify it under the terms of the GNU General Public
  License as published by the Free Software Foundation, version 2.

  This program is distributed in the hope that it will be useful, but WITHOUT
  ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
  FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
  details.

  You should have received a copy of the GNU General Public License along with
  this program; if not, write to the Free Software Foundation, Inc., 51
  Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

  Copyright Buildbot Team Members
*/

import {expect, Page} from "@playwright/test";

export const testPageUrl = 'http://127.0.0.1:8011'

export class BasePage {
  // accessors for elements that all pages have (menu, login, etc)
  static async logOut(page: Page) {
    await page.locator('.navbar-right a.dropdown-toggle').click();
    await page.locator('text=Logout').click();
    await expect(page.locator('.dropdown').first()).toContainText("Anonymous");
  }

  static async loginUser(page: Page, user: string, password: string) {
    await page.goto(`http://${user}:${password}@localhost:8011/auth/login`);
    await BasePage.waitUntilFinishedLoading(page);
    await expect(page.locator('.dropdown').first()).not.toContainText("Anonymous");
  }

  static async waitUntilFinishedLoading(page: Page) {
    await expect.poll(async () => {
      return (await page.getByTestId("loading").count());
    }, {
      message: "Waited until finished loading"
    }).toEqual(0);
  }

  static async waitUntilUrlChanged(page: Page, urlChangeFunction: () => Promise<void>) {
    const url = page.url();
    for (let i = 0; i < 5; ++i) {
      // repeat a few times as just a single action is often insufficient
      await urlChangeFunction();
      for (let j = 0; j < 50; j++) {
        if (page.url() !== url) {
          await BasePage.waitUntilFinishedLoading(page);
          return;
        }
        await page.waitForTimeout(100);
      }
      // make sure URL is checked again just before urlChangeFunction
      if (page.url() !== url) {
        await BasePage.waitUntilFinishedLoading(page);
        return;
      }
    }
    throw new Error('URL has not changed');
  }
}
