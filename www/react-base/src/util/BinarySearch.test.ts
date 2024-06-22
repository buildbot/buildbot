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

import {
  binarySearchEqual,
  binarySearchGreater,
  binarySearchGreaterEqual,
  binarySearchLess,
  binarySearchLessEqual
} from "./BinarySearch";

it("binarySearchGreaterEqual", () => {

  var lb = binarySearchGreaterEqual;

  function checkArray(arr: number[], values: number[]) {
    for(var l=0; l<arr.length; ++l) {
      for(var h=l; h<arr.length; ++h) {
        for(var i=0; i<values.length; ++i) {
          for(var j=l; j<=h; ++j) {
            if(arr[j] >= values[i]) {
              break
            }
          }
          expect(lb(arr, values[i], undefined, l, h)).toEqual(j);
        }
      }
    }
  }

  checkArray([0,1,1,1,2], [-1, 0, 1, 2, 0.5, 1.5, 5])

  expect(lb([0,2,5,6], 0)).toEqual(0);
  expect(lb([0,2,5,6], 1)).toEqual(1);
  expect(lb([0,2,5,6], 2)).toEqual(1);
  expect(lb([0,2,5,6], 3)).toEqual(2);
  expect(lb([0,2,5,6], 4)).toEqual(2);
  expect(lb([0,2,5,6], 5)).toEqual(2);
  expect(lb([0,2,5,6], 6)).toEqual(3);

  function cmp(a: number, b: number) {
    return a - b
  }

  expect(lb([0,1,1,1,2], -1, cmp)).toEqual(0);
  expect(lb([0,1,1,1,2], 0, cmp)).toEqual(0);
  expect(lb([0,1,1,1,2], 1, cmp)).toEqual(1);
  expect(lb([0,1,1,1,2], 2, cmp)).toEqual(4);
  expect(lb([0,1,1,1,2], 0.5, cmp)).toEqual(1);
  expect(lb([0,1,1,1,2], 1.5, cmp)).toEqual(4);
  expect(lb([0,1,1,1,2], 5, cmp)).toEqual(5);

  expect(lb([0,2,5,6], 0, cmp)).toEqual(0);
  expect(lb([0,2,5,6], 1, cmp)).toEqual(1);
  expect(lb([0,2,5,6], 2, cmp)).toEqual(1);
  expect(lb([0,2,5,6], 3, cmp)).toEqual(2);
  expect(lb([0,2,5,6], 4, cmp)).toEqual(2);
  expect(lb([0,2,5,6], 5, cmp)).toEqual(2);
  expect(lb([0,2,5,6], 6, cmp)).toEqual(3);

})

it("binarySearchLess", () => {
  const lu = binarySearchLess;

  function checkArray(arr: number[], values: number[]) {
    for(var l = 0; l < arr.length; ++l) {
      for(var h = l; h < arr.length; ++h) {
        for(var i = 0; i < values.length; ++i) {
          for(var j = h; j>=l; --j) {
            if(values[i] > arr[j]) {
              break
            }
          }
          expect(lu(arr, values[i], undefined, l, h)).toEqual(j);
        }
      }
    }
  }

  checkArray([0,1,1,1,2], [-1, 0, 1, 2, 0.5, 1.5, 5])
});

it("binarySearchGreater", () => {
  const lb = binarySearchGreater;

  function checkArray(arr: number[], values: number[]) {
    for(var l=0; l<arr.length; ++l) {
      for(var h=l; h<arr.length; ++h) {
        for(var i=0; i<values.length; ++i) {
          for(var j=l; j<=h; ++j) {
            if(arr[j] > values[i]) {
              break
            }
          }
          expect(lb(arr, values[i], undefined, l, h)).toEqual(j);
        }
      }
    }
  }

  checkArray([0,1,1,1,2], [-1, 0, 1, 2, 0.5, 1.5, 5])
});

it("binarySearchLessEqual", () => {
  const lu = binarySearchLessEqual;

  function checkArray(arr: number[], values: number[]) {
    for(var i=0; i<values.length; ++i) {
      for(var j=arr.length-1; j>=0; --j) {
        if(values[i] >= arr[j]) {
          break
        }
      }
      expect(lu(arr, values[i])).toEqual(j);
    }
  }

  checkArray([0,1,1,1,2], [-1, 0, 1, 2, 0.5, 1.5, 5]);
})

it("binarySearchEqual", () => {
  const lu = binarySearchEqual;

  function checkArray(arr: number[], values: number[]) {
    for(var i=0; i<values.length; ++i) {
      if(arr.indexOf(values[i]) < 0) {
        expect(lu(arr, values[i])).toEqual(-1);
      } else {
        expect(arr[lu(arr, values[i])]).toEqual(values[i]);
      }
    }
  }

  checkArray([0,1,1,1,2], [-1, 0, 1, 2, 0.5, 1.5, 5])
});
