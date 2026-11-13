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

import { expect, Locator, Page, test } from "@playwright/test";
import { BuilderPage } from "./pages/builder";
import {
  SettingsPage,
  BuildersSettings,
  WaterfallSettings,
  ConsoleSettings,
} from "./pages/settings";

async function goToSettings(page: Page) {
  await BuilderPage.gotoBuildersList(page);
  await SettingsPage.goto(page);
}

async function expectSetting(setting: Locator, value: string | RegExp) {
  await expect(setting).toHaveValue(value);
}

async function setSetting(setting: Locator, value: string) {
  await setting.fill(value);
}

async function setAndExpectSetting(
  page: Page,
  settingGetter: () => Locator,
  value: string,
) {
  await goToSettings(page);
  await setSetting(settingGetter(), value);
  await goToSettings(page);
  await expectSetting(settingGetter(), value);
}

test.describe("manage settings", function () {
  test.describe("base", () => {
    test("Builders.buildFetchLimit uses default value from config", async ({
      page,
    }) => {
      await goToSettings(page);
      await expectSetting(BuildersSettings.buildFetchLimit(page), "201");
    });
  });

  test.describe("waterfall", () => {
    test('change the "scalling factor" and check it', async ({ page }) => {
      const scalingFactor = "10";
      await setAndExpectSetting(
        page,
        () => WaterfallSettings.scalingWaterfall(page),
        scalingFactor,
      );
    });

    test('change the "minimum column width" and check it', async ({ page }) => {
      const scalingWidth = "450";
      await setAndExpectSetting(
        page,
        () => WaterfallSettings.minColumnWidthWaterfall(page),
        scalingWidth,
      );
    });

    test('change the "lazy loading limit" and check it', async ({ page }) => {
      const lazyLoadingLimit = "30";
      await setAndExpectSetting(
        page,
        () => WaterfallSettings.lazyLimitWaterfall(page),
        lazyLoadingLimit,
      );
    });

    test('change the "idle time threshold" and check it', async ({ page }) => {
      const idleTimeThreshold = "15";
      await setAndExpectSetting(
        page,
        () => WaterfallSettings.idleThresholdWaterfall(page),
        idleTimeThreshold,
      );
    });

    test("check that custom ui_default_config from master.cfg is loaded", async ({
      page,
    }) => {
      await goToSettings(page);
      await expectSetting(WaterfallSettings.scalingWaterfall(page), "1.234");
    });
  });

  test.describe("console", () => {
    test('change the "number of builds to fetch" and check it', async ({
      page,
    }) => {
      const buildsToFetch = "130";
      await setAndExpectSetting(
        page,
        () => ConsoleSettings.buildLimit(page),
        buildsToFetch,
      );
    });

    test('change the "number of changes to fetch" and check it', async ({
      page,
    }) => {
      const changesToFetch = "45";
      await setAndExpectSetting(
        page,
        () => ConsoleSettings.changeLimit(page),
        changesToFetch,
      );
    });
  });
});
