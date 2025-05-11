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

import {test, expect} from "@playwright/test";
import {BasePage} from "./pages/base";
import {HomePage} from './pages/home';

test.describe('wsgi', function() {
  test('should navigate to wsgi dashboard page, check the links in the table', async ({page}) => {
    await HomePage.goto(page);
    await expect(page.locator('.bb-sidebar-item').nth(5)).toContainText('Test Dashboard');
    await BasePage.waitUntilUrlChanged(page, async () => {
      await page.locator('.bb-sidebar-item').locator('text=Test Dashboard').click();
    });
    await BasePage.waitUntilFinishedLoading(page);
    await expect.poll(async () => {
        return (await page.locator(".bb-wsgi-dashboard-view")
          .locator('tr').locator('text=slowruntests').count()) !== 0;
      }, {
        message: "did not load builders to the dashboard"
      }).toBeTruthy();
  });
});
