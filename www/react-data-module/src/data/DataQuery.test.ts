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

import DataQuery, {Query} from "./DataQuery";

class WrappedDataQuery {
  filter(array: any[], query: Query) {
    const q = new DataQuery(query);
    array = [...array];
    q.filter(array);
    return array;
  }

  sort(array: any[], order: any) {
    const q = new DataQuery({order});
    array = [...array];
    q.sort(array, order);
    return array;
  }
  limit(array: any[], limit: number) {
    const q = new DataQuery({limit});
    array = [...array];
    q.limit(array, limit);
    return array;
  }
}

describe('dataquery service', () => {
  let testArray: any[] = [];
  let wrappedDataQuery = new WrappedDataQuery();

  beforeEach(() => {
    testArray = [{
        builderid: 1,
        buildid: 3,
        buildrequestid: 1,
        complete: false,
        complete_at: null,
        started_at: 1417802797
      }, {
        builderid: 2,
        buildid: 1,
        buildrequestid: 1,
        complete: true,
        complete_at: 1417803429,
        started_at: 1417803026
      }, {
        builderid: 1,
        buildid: 2,
        buildrequestid: 1,
        complete: true,
        complete_at: 1417803038,
        started_at: 1417803025
      }
    ];
  });

  describe('filter(array, filters)', () => {

    it('should filter the array (one filter)', () => {
      const result = wrappedDataQuery.filter(testArray, {complete: false});
      expect(result.length).toBe(1);
      expect(result).toContain(testArray[0]);
    });

    it('should filter the array (more than one filters)', () => {
      const result = wrappedDataQuery.filter(testArray, {complete: true, buildrequestid: 1});
      expect(result.length).toBe(2);
      expect(result).toContain(testArray[1]);
      expect(result).toContain(testArray[2]);
    });

    it('should filter the array (eq - equal)', () => {
      const result = wrappedDataQuery.filter(testArray, {'complete__eq': true});
      expect(result.length).toBe(2);
      expect(result).toContain(testArray[1]);
      expect(result).toContain(testArray[2]);
    });

    it('should filter the array (two eq)', () => {
      const result = wrappedDataQuery.filter(testArray, {'buildid__eq': [1, 2]});
      expect(result.length).toBe(2);
      expect(result).toContain(testArray[1]);
      expect(result).toContain(testArray[2]);
    });

    it('should treat empty eq criteria as no restriction', () => {
      const result = wrappedDataQuery.filter(testArray, {'buildid__eq': []});
      expect(result.length).toBe(3);
    });

    it('should filter the array (ne - not equal)', () => {
      const result = wrappedDataQuery.filter(testArray, {'complete__ne': true});
      expect(result.length).toBe(1);
      expect(result).toContain(testArray[0]);
    });

    it('should filter the array (lt - less than)', () => {
      const result = wrappedDataQuery.filter(testArray, {'buildid__lt': 3});
      expect(result.length).toBe(2);
      expect(result).toContain(testArray[1]);
      expect(result).toContain(testArray[2]);
    });

    it('should filter the array (le - less than or equal to)', () => {
      const result = wrappedDataQuery.filter(testArray, {'buildid__le': 3});
      expect(result.length).toBe(3);
    });

    it('should filter the array (gt - greater than)', () => {
      const result = wrappedDataQuery.filter(testArray, {'started_at__gt': 1417803025});
      expect(result.length).toBe(1);
      expect(result).toContain(testArray[1]);
    });

    it('should filter the array (ge - greater than or equal to)', () => {
      const result = wrappedDataQuery.filter(testArray, {'started_at__ge': 1417803025});
      expect(result.length).toBe(2);
      expect(result).toContain(testArray[1]);
      expect(result).toContain(testArray[2]);
    });

    it('should convert on/off, true/false, yes/no to boolean', () => {
      const resultTrue = wrappedDataQuery.filter(testArray, {complete: true});
      const resultFalse = wrappedDataQuery.filter(testArray, {complete: false});

      let result = wrappedDataQuery.filter(testArray, {complete: 'on'});
      expect(result).toEqual(resultTrue);
      result = wrappedDataQuery.filter(testArray, {complete: 'true'});
      expect(result).toEqual(resultTrue);
      result = wrappedDataQuery.filter(testArray, {complete: 'yes'});
      expect(result).toEqual(resultTrue);

      result = wrappedDataQuery.filter(testArray, {complete: 'off'});
      expect(result).toEqual(resultFalse);
      result = wrappedDataQuery.filter(testArray, {complete: 'false'});
      expect(result).toEqual(resultFalse);
      result = wrappedDataQuery.filter(testArray, {complete: 'no'});
      expect(result).toEqual(resultFalse);
    });
  });

  describe('sort(array, order)', () => {

    it('should sort the array (one parameter)', () => {
      const result = wrappedDataQuery.sort(testArray, 'buildid');
      expect(result[0]).toEqual(testArray[1]);
      expect(result[1]).toEqual(testArray[2]);
      expect(result[2]).toEqual(testArray[0]);
    });

    it('should sort the array (one parameter, - reverse)', () => {
      const result = wrappedDataQuery.sort(testArray, '-buildid');
      expect(result[0]).toEqual(testArray[0]);
      expect(result[1]).toEqual(testArray[2]);
      expect(result[2]).toEqual(testArray[1]);
    });

    it('should sort the array (more parameter)', () => {
      const result = wrappedDataQuery.sort(testArray, ['builderid', '-buildid']);
      expect(result[0]).toEqual(testArray[0]);
      expect(result[1]).toEqual(testArray[2]);
      expect(result[2]).toEqual(testArray[1]);
    });
  });

  describe('limit(array, limit)', () => {

    it('should slice the array', () => {
      const result = wrappedDataQuery.limit(testArray, 1);
      expect(result.length).toBe(1);
      expect(result[0]).toEqual(testArray[0]);
    });

    it('should return the array when the limit >= array.length', () => {
      const result = wrappedDataQuery.limit(testArray, 3);
      expect(result.length).toBe(3);
      expect(result[2]).toEqual(testArray[2]);
    });
  });
});
