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

import { Pagination } from "react-bootstrap";
import { clamp } from "./Math";

export function makePagination<T>(
  currentPage: number, setCurrentPage: (pageIdx: number) => void,
  pageSize: number,
  data: T[],
): [T[], JSX.Element] {
  // show pagination for 2 before/after current
  const pageRange = 2;

  const pageCount = Math.max(Math.ceil(data.length / pageSize), 1);
  const clampedPage = clamp(currentPage, 1, pageCount);

  const displayItemBegin = Math.max(clampedPage - pageRange, 1);
  const displayItemEnd = Math.min(clampedPage + pageRange, pageCount);
  const pageItemIndexes = Array.from(
    Array(displayItemEnd - displayItemBegin + 1),
    (_, i)=> i + displayItemBegin
  );
  const isFirstPage = clampedPage <= 1;
  const isLastPage = clampedPage >= pageCount;

  const onGoTo = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter") {
      event.preventDefault();

      const target = event.target as HTMLInputElement;
      const value = Number.parseInt(target.value);
      if (!Number.isNaN(value)) {
        setCurrentPage(clamp(value, 1, pageCount));
      }
    }
  };

  return [
    data.slice((clampedPage - 1) * pageSize, clampedPage * pageSize),
    (
      <Pagination>
        <Pagination.First disabled={isFirstPage} onClick={_ => { if (!isFirstPage) { setCurrentPage(1); } } } />
        <Pagination.Prev disabled={isFirstPage} onClick={_ => { if (!isFirstPage) { setCurrentPage(clampedPage - 1); } } } />

        {pageItemIndexes.at(0) !== 1 ? <Pagination.Ellipsis /> : <></>}

        {
          pageItemIndexes.map(itemIdx => {
            return (
              <Pagination.Item
                key={itemIdx}
                active={itemIdx === clampedPage}
                onClick={_ => setCurrentPage(itemIdx)}
              >
                {itemIdx}
              </Pagination.Item>
            );
          })
        }

        {pageItemIndexes.at(-1) !== pageCount ? <Pagination.Ellipsis /> : <></>}

        <Pagination.Next disabled={isLastPage} onClick={_ => { if (!isLastPage) { setCurrentPage(clampedPage + 1); } } } />
        <Pagination.Last disabled={isLastPage} onClick={_ => { if (!isLastPage) { setCurrentPage(pageCount); } } } />

        <input
          data-bb-test-id="pagination-goto-input"
          type="number"
          min={1} max={pageCount}
          placeholder="go to" enterKeyHint="go" onKeyDown={onGoTo}
          size={Math.max(pageCount.toString().length, 5)}
          disabled={pageCount <= 1}
        />
      </Pagination>
    )
  ];
};
