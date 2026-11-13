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

import { Page } from "@playwright/test";
import { BasePage } from "./base";

export class SettingsPage {
  static async goto(page: Page) {
    await page.goto("/#/settings");
    await BasePage.waitUntilFinishedLoading(page);
  }

  static getItem(page: Page, group: string, name: string) {
    return page
      .getByTestId(`settings-group-${group}`)
      .getByTestId(`settings-field-${name}`);
  }
}

export class BuildersSettings {
  static buildFetchLimit(page: Page) {
    return SettingsPage.getItem(page, "Builders", "buildFetchLimit");
  }
}

export class WaterfallSettings {
  static scalingWaterfall(page: Page) {
    return SettingsPage.getItem(page, "Waterfall", "scaling_waterfall");
  }

  static minColumnWidthWaterfall(page: Page) {
    return SettingsPage.getItem(
      page,
      "Waterfall",
      "min_column_width_waterfall",
    );
  }
  static lazyLimitWaterfall(page: Page) {
    return SettingsPage.getItem(page, "Waterfall", "lazy_limit_waterfall");
  }
  static idleThresholdWaterfall(page: Page) {
    return SettingsPage.getItem(page, "Waterfall", "idle_threshold_waterfall");
  }
}

export class ConsoleSettings {
  static buildLimit(page: Page) {
    return SettingsPage.getItem(page, "Console", "buildLimit");
  }
  static changeLimit(page: Page) {
    return SettingsPage.getItem(page, "Console", "changeLimit");
  }
}
