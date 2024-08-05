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
import {fillTemplate, parseTemplate} from "./TemplateFormat";

describe('TemplateFormat', () => {
  describe('parseTemplate', () => {
    it('empty', () => {
      expect(parseTemplate('')).toEqual({
        template: '',
        replacements: new Set<string>(),
        errors: []
      });
    });

    it('no replacements', () => {
      expect(parseTemplate('no replacements')).toEqual({
        template: 'no replacements',
        replacements: new Set<string>(),
        errors: []
      });
    });

    it('single replacement', () => {
      expect(parseTemplate('%(replacement)')).toEqual({
        template: '%(replacement)',
        replacements: new Set(['replacement']),
        errors: []
      });
      expect(parseTemplate('abc%(replacement)')).toEqual({
        template: 'abc%(replacement)',
        replacements: new Set(['replacement']),
        errors: []
      });
      expect(parseTemplate('%(replacement)abc')).toEqual({
        template: '%(replacement)abc',
        replacements: new Set(['replacement']),
        errors: []
      });
    });

    it('empty replacement', () => {
      expect(parseTemplate('%()')).toEqual({
        template: '%()',
        replacements: new Set(),
        errors: ['Empty replacement at position 0']
      });
    });

    it('two replacements', () => {
      expect(parseTemplate('%(r1)%(r2)')).toEqual({
        template: '%(r1)%(r2)',
        replacements: new Set(['r1', 'r2']),
        errors: []
      });
      expect(parseTemplate('%(r1)a%(r2)')).toEqual({
        template: '%(r1)a%(r2)',
        replacements: new Set(['r1', 'r2']),
        errors: []
      });
      expect(parseTemplate('a%(r1)%(r2)')).toEqual({
        template: 'a%(r1)%(r2)',
        replacements: new Set(['r1', 'r2']),
        errors: []
      });
      expect(parseTemplate('%(r1)%(r2)a')).toEqual({
        template: '%(r1)%(r2)a',
        replacements: new Set(['r1', 'r2']),
        errors: []
      });
    });
  });

  describe('fillTemplate', () => {
    it('empty', () => {
      expect(fillTemplate('', new Map<string, string>())).toEqual('');
    });

    it('no replacements', () => {
      expect(fillTemplate('no replacements', new Map<string, string>())).toEqual('no replacements');
      expect(fillTemplate('no replacements', new Map<string, string>([['no', 'with']])))
        .toEqual('no replacements');
    });

    it('single replacement', () => {
      expect(fillTemplate('%(repl)', new Map<string, string>([['repl', 'value']])))
        .toEqual('value');
      expect(fillTemplate('%(repl)', new Map<string, string>()))
        .toEqual('');
      expect(fillTemplate('abc%(repl)', new Map<string, string>([['repl', 'value']])))
        .toEqual('abcvalue');
      expect(fillTemplate('abc%(repl)', new Map<string, string>()))
        .toEqual('abc');
      expect(fillTemplate('%(repl)abc', new Map<string, string>([['repl', 'value']])))
        .toEqual('valueabc');
      expect(fillTemplate('%(repl)abc', new Map<string, string>()))
        .toEqual('abc');
    });

    it('two replacements', () => {
      expect(fillTemplate(
        '%(r1)%(r2)',
        new Map<string, string>([['r1', 'value1'], ['r2', 'value2']])
      )).toEqual('value1value2');

      expect(fillTemplate(
        '%(r1)a%(r2)',
        new Map<string, string>([['r1', 'value1'], ['r2', 'value2']])
      )).toEqual('value1avalue2');

      expect(fillTemplate(
        'a%(r1)%(r2)',
        new Map<string, string>([['r1', 'value1'], ['r2', 'value2']])
      )).toEqual('avalue1value2');

      expect(fillTemplate(
        '%(r1)%(r2)a',
        new Map<string, string>([['r1', 'value1'], ['r2', 'value2']])
      )).toEqual('value1value2a');
    });
  });
});
