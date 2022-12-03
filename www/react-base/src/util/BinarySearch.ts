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
/* The MIT License (MIT)

Copyright (c) 2013-2015 Mikola Lysenko

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE. */

export function binarySearchGreaterEqual<T, U>(a: ArrayLike<T>, y: U, c?: (a: T, y: U) => number,
                                               lo?: number, hi?: number) {
  let l = (lo === undefined) ? 0 : lo | 0;
  let h = (hi === undefined) ? a.length - 1 : hi | 0;

  var i = h + 1;
  while (l <= h) {
    var m = (l + h) >>> 1, x = a[m];
    var p = (c !== undefined) ? c(x, y) : ((x as unknown as number) - (y as unknown as number));
    if (p >= 0) {
      i = m;
      h = m - 1
    } else {
      l = m + 1
    }
  }
  return i;
};

export function binarySearchGreater<T, U>(a: ArrayLike<T>, y: U, c?: (a: T, y: U) => number,
                                          lo?: number, hi?: number) {
  let l = (lo === undefined) ? 0 : lo | 0;
  let h = (hi === undefined) ? a.length - 1 : hi | 0;

  var i = h + 1;
  while (l <= h) {
    var m = (l + h) >>> 1, x = a[m];
    var p = (c !== undefined) ? c(x, y) : ((x as unknown as number) - (y as unknown as number));
    if (p > 0) {
      i = m;
      h = m - 1;
    } else {
      l = m + 1;
    }
  }
  return i;
};

export function binarySearchLess<T, U>(a: ArrayLike<T>, y: U, c?: (a: T, y: U) => number,
                                       lo?: number, hi?: number) {
  let l = (lo === undefined) ? 0 : lo | 0;
  let h = (hi === undefined) ? a.length - 1 : hi | 0;

  var i = l - 1;
  while (l <= h) {
    var m = (l + h) >>> 1, x = a[m];
    var p = (c !== undefined) ? c(x, y) : ((x as unknown as number) - (y as unknown as number));
    if (p < 0) {
      i = m;
      l = m + 1;
    } else {
      h = m - 1;
    }
  }
  return i;
};

export function binarySearchLessEqual<T, U>(a: ArrayLike<T>, y: U, c?: (a: T, y: U) => number,
                                            lo?: number, hi?: number) {
  let l = (lo === undefined) ? 0 : lo | 0;
  let h = (hi === undefined) ? a.length - 1 : hi | 0;

  var i = l - 1;
  while (l <= h) {
    var m = (l + h) >>> 1, x = a[m];
    var p = (c !== undefined) ? c(x, y) : ((x as unknown as number) - (y as unknown as number));
    if (p <= 0) {
      i = m;
      l = m + 1;
    } else {
      h = m - 1;
    }
  }
  return i;
}

export function binarySearchEqual<T, U>(a: ArrayLike<T>, y: U, c?: (a: T, y: U) => number,
                                        lo?: number, hi?: number) {
  let l = (lo === undefined) ? 0 : lo | 0;
  let h = (hi === undefined) ? a.length - 1 : hi | 0;

  while (l <= h) {
    var m = (l + h) >>> 1, x = a[m];
    var p = (c !== undefined) ? c(x, y) : ((x as unknown as number) - (y as unknown as number));
    if (p === 0) { return m }
    if (p <= 0) {
      l = m + 1;
    } else {
      h = m - 1;
    }
  }
  return -1;
}
