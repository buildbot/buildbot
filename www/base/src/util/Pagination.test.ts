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

import {describe, expect, it} from "vitest";
import {render} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {makePagination} from "./Pagination";

describe('makePagination', () => {
  it('disable if unnecessary ', () => {
    let currentPage = 1;
    const paginationElement = makePagination(
      currentPage, (p) => { currentPage = p; },
      2, [],
    )[1];
    expect(render(paginationElement).asFragment()).toMatchSnapshot();
  });

  it('out of bounds', () => {
    let currentPage = 150;
    const paginationElement = makePagination(
      currentPage, (p) => { currentPage = p; },
      2, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'.split('')
    )[1];
    // pagination item '18' should be active
    expect(render(paginationElement).asFragment()).toMatchSnapshot();
  });

  it('paginate data', () => {
    let currentPage = 2;
    const [paginatedData, paginationElement] = makePagination(
      currentPage, (p) => { currentPage = p; },
      2, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'.split('')
    );
    expect(render(paginationElement).asFragment()).toMatchSnapshot();
    expect(paginatedData).toEqual(['C', 'D']);
  });

  it('go to page on input', async () => {
    let currentPage = 1;
    const paginationElement = makePagination(
      currentPage, (p) => { currentPage = p; },
      2, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'.split('')
    )[1];

    const renderedElement = render(paginationElement);
    const gotoInput = renderedElement.getByTestId('pagination-goto-input') as HTMLInputElement;
    await userEvent.type(gotoInput, "3");
    // don't go to page on type to avoid reload
    expect(currentPage).toBe(1);
    // goto on user validation (enter pressed)
    await userEvent.type(gotoInput, "{enter}");
    expect(currentPage).toBe(3);
  });
});
