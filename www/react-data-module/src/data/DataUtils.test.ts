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

import {
  capitalize,
  copyOrSplit,
  emailInString,
  endpointPath,
  numberOrString,
  parse,
  restPath,
  singularType,
  socketPath,
  socketPathRE,
  type
} from "./DataUtils";

describe('Data utils service', function() {
  describe('capitalize(string)', () =>

    it('should capitalize the parameter string', function() {
      let result = capitalize('test');
      expect(result).toBe('Test');

      result = capitalize('t');
      expect(result).toBe('T');
    })
  );

  describe('type(arg)', () =>

    it('should return the type of the parameter endpoint', function() {
      let result = type('asd/1');
      expect(result).toBe('asd');

      result = type('asd/1/bnm');
      expect(result).toBe('bnm');
    })
  );

  describe('singularType(arg)', () =>

    it('should return the singular the type name of the parameter endpoint', function() {
      let result = singularType('tests/1');
      expect(result).toBe('test');

      result = singularType('tests');
      expect(result).toBe('test');
    })
  );

  describe('socketPath(arg)', () =>

    it('should return the WebSocket subscribe path of the parameter path', function() {
      let result = socketPath('asd/1/bnm');
      expect(result).toBe('asd/1/bnm/*/*');

      result = socketPath('asd/1');
      expect(result).toBe('asd/1/*');
    })
  );

  describe('socketPathRE(arg)', () =>

    it('should return the WebSocket subscribe path of the parameter path', function() {
      let result = socketPathRE('asd/1/*');
      expect(result.test("asd/1/new")).toBeTruthy();

      let source = socketPathRE('asd/1/bnm/*/*').source;
      expect([
        '^asd\\/1\\/bnm\\/[^\\/]+\\/[^\\/]+$',
        '^asd\\/1\\/bnm\\/[^/]+\\/[^/]+$'
      ]).toContain(source);

      source = socketPathRE('asd/1/*').source;
      expect([
        '^asd\\/1\\/[^\\/]+$',
        '^asd\\/1\\/[^/]+$'
      ]).toContain(source);
    })
  );


  describe('restPath(arg)', () =>

    it('should return the rest path of the parameter WebSocket subscribe path', function() {
      let result = restPath('asd/1/bnm/*/*');
      expect(result).toBe('asd/1/bnm');

      result = restPath('asd/1/*');
      expect(result).toBe('asd/1');
    })
  );

  describe('endpointPath(arg)', () =>

    it('should return the endpoint path of the parameter rest or WebSocket path', function() {
      let result = endpointPath('asd/1/bnm/*/*');
      expect(result).toBe('asd/1/bnm');

      result = endpointPath('asd/1/*');
      expect(result).toBe('asd');
    })
  );

  describe('copyOrSplit(arrayOrString)', function() {

    it('should copy an array', function() {
      const array = [1, 2, 3];
      const result = copyOrSplit(array);
      expect(result).not.toBe(array);
      expect(result).toEqual(array);
    });

    it('should split a string', function() {
      const string = 'asd/123/bnm';
      const result = copyOrSplit(string);
      expect(result).toEqual(['asd', '123', 'bnm']);
    });
  });

  describe('parse(object)', () =>

    it('should parse fields from JSON', function() {
      const test = {
        a: 1,
        b: 'asd3',
        c: JSON.stringify(['a', 1, 2]),
        d: JSON.stringify({asd: [], bsd: {}})
      };

      const copy = JSON.parse(JSON.stringify(test));
      copy.c = JSON.stringify(copy.c);
      copy.d = JSON.stringify(copy.d);

      const parsed = parse(test);

      expect(parsed).toEqual(test);
    })
  );

  describe('numberOrString(string)', function() {

    it('should convert a string to a number if possible', function() {
      const result = numberOrString('12');
      expect(result).toBe(12);
    });

    it('should throw if it is not a number', function() {
      expect(() => numberOrString('w3as')).toThrow();
    });
  });

  describe('emailInString(string)', () =>

    it('should return an email from a string', function() {
      let email = emailInString('foo <bar@foo.com>');
      expect(email).toBe('bar@foo.com');
      email = emailInString('bar@foo.com');
      expect(email).toBe('bar@foo.com');
    })
  );
});
