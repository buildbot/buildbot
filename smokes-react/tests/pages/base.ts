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
    await urlChangeFunction();
    await expect.poll(async () => page.url(), {message: "URL changed"}).not.toEqual(url);
  }
}
