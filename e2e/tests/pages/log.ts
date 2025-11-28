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

import { expect, Page } from "@playwright/test";

export class LogPage {

  static async openFullStdioFromSummary(page: Page, stepName: string) {
    // Ensure build summary is visible
    await expect(page.locator('.bb-build-summary')).toBeVisible();

    // Find the step
    const step = page.locator('.bb-build-summary-step-line', { hasText: stepName }).first();
    await expect(step).toBeVisible();

    // Toggle the step open if not already
    const preview = step.locator('.logpreview');
    if (!(await preview.isVisible())) {
      await step.scrollIntoViewIfNeeded();
      const caret = step.locator(':scope > div .rotate.clickable').first();
      await expect(caret).toBeVisible();
      await caret.click();
    }

    // Wait for preview contents to render
    await expect(preview.locator('.bb-log-preview-contents')).toBeVisible();

    // Find and click "view all … lines"
    const viewAll = preview.locator('.bb-log-preview-download a[href*="/logs/stdio"]').first();
    await expect(viewAll).toBeVisible({ timeout: 30000 });
    await viewAll.click();
  }

  static async waitForStdioUrl(page: Page) {
    await page.waitForURL(/\/#\/builders\/\d+\/builds\/\d+\/steps\/\d+\/logs\/stdio$/);
  }

  static async search(page: Page, term: string) {
    const searchInput = page.locator('.bb-log-search-field-text').first()
    await expect(searchInput).toBeVisible();
    await searchInput.pressSequentially(term, {"delay": 10});
  }

  static async assertNoAnsiInOutput(page: Page) {
    // ANSI sequence are expected in .log_h, but not in .log_o
    const rows = page.locator('.bb-logviewer-text-row > span.log_o');
    await expect.poll(async () => await rows.count()).toBeGreaterThanOrEqual(5);
    const offenders = page.locator('.bb-logviewer-text-row > span.log_o', {hasText: /\u001b\[/});
    await expect(offenders).toHaveCount(0);
  }


  static async assertSearchHighlight(page: Page, searchTerm: string) {
    // Row should be highlighted and visible, highlighted text should be the search term
    const row = page.locator('.bb-logviewer-text-row:has(.bb-logviewer-result-current)').first();
    await expect(row).toBeVisible();
    const highlights = row.locator('.bb-logviewer-result-current');
    await expect.poll(() => highlights.count()).toBeGreaterThan(0);
    const texts = await highlights.allTextContents();
    const highlightedText = texts.join('');
    expect(highlightedText).toBe(searchTerm);
  }

}
