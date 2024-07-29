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

import { AboutPage } from './pages/about';
import { test, expect } from '@playwright/test';

test('about page should contain default elements inside', async ({page}) => {
  await AboutPage.goto(page);
  await expect(page.locator('h2').first()).toContainText("About this");
  await expect(page.locator('h2').first()).toContainText("buildbot");
  await expect(page.locator('h2').nth(1)).toContainText("Configuration");
  await expect(page.locator('h2').nth(2)).toContainText("API description");
});
