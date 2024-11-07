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
import {
  ansi2html,
  generateStyleElement,
  parseAnsiSgrEntry,
  parseEscapeCodesToClasses, stripAnsiSgrEntry, stripLineEscapeCodes,
} from "./AnsiEscapeCodes";
import {render} from '@testing-library/react';

describe('AnsiEscapeCodes', () => {

  describe('stripAnsiSgrEntry', () => {
    const runTest = (ansi: string, expectedEntry: string) => {
      expect(stripAnsiSgrEntry(ansi)).toEqual(expectedEntry);
    };

    it("test_ansi0m", () => runTest("mfoo", "foo"));

    it("test ansi1m", () => runTest("33mfoo", "foo"));

    it("test ansi2m", () => runTest("1;33mfoo", "foo"));

    it("test ansi5m", () => runTest("1;2;3;4;33mfoo", "foo"));

    it("test ansi_notm", () => runTest("33xfoo", "foo"));

    it("test ansi_invalid", () => runTest("<>foo", "\x1b[<>foo"));

    it("test ansi_invalid_start_by_semicolon", () => runTest(";3m", "\x1b[;3m"));
  });

  describe('parseAnsiSgrEntry', () => {
    const runTest = (ansi: string, expectedEntry: string, expectedClasses: string[]) => {
      expect(parseAnsiSgrEntry(ansi)).toEqual([expectedEntry, expectedClasses]);
    };

    it("test_ansi0m", () => runTest("mfoo", "foo", []));

    it("test ansi1m", () => runTest("33mfoo", "foo", ["33"]));

    it("test ansi2m", () => runTest("1;33mfoo", "foo", ["1", "33"]));

    it("test ansi5m", () => runTest("1;2;3;4;33mfoo", "foo", ["1", "2", "3", "4", "33"]));

    it("test ansi_notm", () => runTest("33xfoo", "foo", []));

    it("test ansi_invalid", () => runTest("<>foo", "\x1b[<>foo", []));

    it("test ansi_invalid_start_by_semicolon", () => runTest(";3m", "\x1b[;3m", []));
  });

  describe('stripLineEscapeCodes', () => {
    it('simple', () => {
      const ret = stripLineEscapeCodes(
        "\x1b[36mDEBUG [plugin]: \x1b[39mLoading plugin karma-jasmine.");
      expect(ret).toEqual("DEBUG [plugin]: Loading plugin karma-jasmine.");
    });

    it('with reset codes', () => {
      // code sequence from protractor
      const ret = stripLineEscapeCodes("\x1b[32m.\x1b[0m\x1b[31mF\x1b[0m\x1b[32m.\x1b[39m\x1b[32m.\x1b[0m");
      expect(ret).toEqual(".F..");
    });

    it('256 colors', () => {
      const ret = stripLineEscapeCodes(
        "\x1b[48;5;71mDEBUG \x1b[38;5;72m[plugin]: \x1b[39mLoading plugin karma-jasmine.");
      expect(ret).toEqual("DEBUG [plugin]: Loading plugin karma-jasmine.");
    });

    it('joint codes', () => {
      const ret = stripLineEscapeCodes(
        "\x1b[1;36mDEBUG [plugin]: \x1b[39mLoading plugin karma-jasmine.");
      expect(ret).toEqual('DEBUG [plugin]: Loading plugin karma-jasmine.');
    });

    it('unsupported modes', () => {
      const val = "\x1b[1A\x1b[2KPhantomJS 1.9.8 (Linux 0.0.0)";
      const ret = stripLineEscapeCodes(val);
      expect(ret).toEqual('PhantomJS 1.9.8 (Linux 0.0.0)');
    });
  });

  describe('parseEscapeCodesToClasses', () => {
    const parseEscapeCodesToSimple = (line: string) => {
      const [text, classes] = parseEscapeCodesToClasses(line);
      if (classes === null) {
        return {
          text: text,
          class: '',
        }
      }
      return classes.map(code => {
        return {
          text: text.slice(code.firstPos, code.lastPos),
          class: code.cssClasses
        }
      });
    }

    it('simple', () => {
      const ret = parseEscapeCodesToSimple(
        "\x1b[36mDEBUG [plugin]: \x1b[39mLoading plugin karma-jasmine.");
      expect(ret).toEqual([
        {class: "ansi36", text: "DEBUG [plugin]: "},
        {class: "", text: "Loading plugin karma-jasmine."},
      ]);
    });

    it('with reset codes', () => {
      // code sequence from protractor
      const ret = parseEscapeCodesToSimple("\x1b[32m.\x1b[0m\x1b[31mF\x1b[0m\x1b[32m.\x1b[39m\x1b[32m.\x1b[0m");
      expect(ret).toEqual([
        {class: "ansi32", text: "."},
        {class: "ansi31", text: "F"},
        {class: "ansi32", text: "."},
        {class: "ansi32", text: "."},
      ]);
    });

    it('with empty reset code', () => {
      // code sequence from protractor
      const ret = parseEscapeCodesToSimple("\x1b[32m.\x1b[m\x1b[31mF\x1b[m\x1b[32m.\x1b[39m\x1b[32m.\x1b[m");
      expect(ret).toEqual([
        {class: "ansi32", text: "."},
        {class: "ansi31", text: "F"},
        {class: "ansi32", text: "."},
        {class: "ansi32", text: "."},
      ]);
    });

    it('256 colors', () => {
      const ret = parseEscapeCodesToSimple(
        "\x1b[48;5;71mDEBUG \x1b[38;5;72m[plugin]: \x1b[39mLoading plugin karma-jasmine.");
      expect(ret).toEqual([
        {class: 'ansibg-71', text: 'DEBUG '},
        {class: 'ansifg-72', text: '[plugin]: '},
        {class: '', text: 'Loading plugin karma-jasmine.'}]);
    });

    it('SGRbg-SGRbg', () => {
      const ret = parseEscapeCodesToSimple(
        "\x1b[42mTEXT1 \x1b[43mTEXT2 \x1b[0m");
      expect(ret).toEqual([
        {class: 'ansi42', text: 'TEXT1 '},
        {class: 'ansi42 ansi43', text: 'TEXT2 '},
        ]);
    });

    it('SGRbg-SGRfg', () => {
      const ret = parseEscapeCodesToSimple(
        "\x1b[42mTEXT1 \x1b[31mTEXT2 \x1b[0m");
      expect(ret).toEqual([
        {class: 'ansi42', text: 'TEXT1 '},
        {class: 'ansi42 ansi31', text: 'TEXT2 '},
      ]);
    });

    it('SGRbg-SGRboth', () => {
      const ret = parseEscapeCodesToSimple(
        "\x1b[42mTEXT1 \x1b[43;31mTEXT2 \x1b[0m");
      expect(ret).toEqual([
        {class: 'ansi42', text: 'TEXT1 '},
        {class: 'ansi42 ansi43 ansi31', text: 'TEXT2 '},
      ]);
    });

    it('SGRbg-256bg', () => {
      const ret = parseEscapeCodesToSimple(
        "\x1b[42mTEXT1 \x1b[48;5;34mTEXT2 \x1b[0m");
      expect(ret).toEqual([
        {class: 'ansi42', text: 'TEXT1 '},
        {class: 'ansibg-34', text: 'TEXT2 '},
      ]);
    });

    it('SGRbg-256fg', () => {
      const ret = parseEscapeCodesToSimple(
        "\x1b[42mTEXT1 \x1b[38;5;226mTEXT2 \x1b[0m");
      expect(ret).toEqual([
        {class: 'ansi42', text: 'TEXT1 '},
        {class: 'ansifg-226', text: 'TEXT2 '},
      ]);
    });

    it('SGRbg-256both', () => {
      const ret = parseEscapeCodesToSimple(
        "\x1b[42mTEXT1 \x1b[48;5;164;38;5;226mTEXT2 \x1b[0m");
      expect(ret).toEqual([
        {class: 'ansi42', text: 'TEXT1 '},
        {class: '', text: 'TEXT2 '},
      ]);
    });

    it('SGRbg-reset0m', () => {
      const ret = parseEscapeCodesToSimple(
        "\x1b[42mTEXT1 \x1b[0mTEXT2 \x1b[0m");
      expect(ret).toEqual([
        {class: 'ansi42', text: 'TEXT1 '},
        {class: '', text: 'TEXT2 '},
      ]);
    });

    it('SGRbg-resetm', () => {
      const ret = parseEscapeCodesToSimple(
        "\x1b[42mTEXT1 \x1b[mTEXT2 \x1b[0m");
      expect(ret).toEqual([
        {class: 'ansi42', text: 'TEXT1 '},
        {class: '', text: 'TEXT2 '},
      ]);
    });

    it('SGRfg-SGRbg', () => {
      const ret = parseEscapeCodesToSimple(
        "\x1b[31mTEXT1 \x1b[42mTEXT2 \x1b[0m");
      expect(ret).toEqual([
        {class: 'ansi31', text: 'TEXT1 '},
        {class: 'ansi31 ansi42', text: 'TEXT2 '},
      ]);
    });

    it('SGRfg-SGRfg', () => {
      const ret = parseEscapeCodesToSimple(
        "\x1b[31mTEXT1 \x1b[32mTEXT2 \x1b[0m");
      expect(ret).toEqual([
        {class: 'ansi31', text: 'TEXT1 '},
        {class: 'ansi31 ansi32', text: 'TEXT2 '},
      ]);
    });

    it('SGRfg-SGRboth', () => {
      const ret = parseEscapeCodesToSimple(
        "\x1b[31mTEXT1 \x1b[42;32mTEXT2 \x1b[0m"); // pridėti kitą bg spalvą¸kad parodytų, kaip permuša? Nebent vėliau permušantis testas bus
      expect(ret).toEqual([
        {class: 'ansi31', text: 'TEXT1 '},
        {class: 'ansi31 ansi42 ansi32', text: 'TEXT2 '},
      ]);
    });

    it('SGRfg-256bg', () => {
      const ret = parseEscapeCodesToSimple(
        "\x1b[31mTEXT1 \x1b[48;5;34mTEXT2 \x1b[0m"); // pridėta pirmojo bg permušanti spalva
      expect(ret).toEqual([
        {class: 'ansi31', text: 'TEXT1 '},
        {class: 'ansibg-34', text: 'TEXT2 '},
      ]);
    });

    it('SGRfg-256fg', () => {
      const ret = parseEscapeCodesToSimple(
        "\x1b[31mTEXT1 \x1b[38;5;226mTEXT2 \x1b[0m");
      expect(ret).toEqual([
        {class: 'ansi31', text: 'TEXT1 '},
        {class: 'ansifg-226', text: 'TEXT2 '},
      ]);
    });

    it('SGRfg-256both', () => {
      const ret = parseEscapeCodesToSimple(
        "\x1b[31mTEXT1 \x1b[48;5;164;38;5;226mTEXT2 \x1b[0m");
      expect(ret).toEqual([
        {class: 'ansi31', text: 'TEXT1 '},
        {class: '', text: 'TEXT2 '},
      ]);
    });

    it('SGRfg-reset0m', () => {
      const ret = parseEscapeCodesToSimple(
        "\x1b[31mTEXT1 \x1b[0mTEXT2 \x1b[0m");
      expect(ret).toEqual([
        {class: 'ansi31', text: 'TEXT1 '},
        {class: '', text: 'TEXT2 '},
      ]);
    });

    it('SGRfg-resetm', () => {
      const ret = parseEscapeCodesToSimple(
        "\x1b[31mTEXT1 \x1b[mTEXT2 \x1b[0m");
      expect(ret).toEqual([
        {class: 'ansi31', text: 'TEXT1 '},
        {class: '', text: 'TEXT2 '},
      ]);
    });

    it('SGRboth-SGRbg', () => {
      const ret = parseEscapeCodesToSimple(
        "\x1b[42;31mTEXT1 \x1b[43mTEXT2 \x1b[0m");
      expect(ret).toEqual([
        {class: 'ansi42 ansi31', text: 'TEXT1 '},
        {class: 'ansi42 ansi31 ansi43', text: 'TEXT2 '},
      ]);
    });

    it('SGRboth-SGRfg', () => {
      const ret = parseEscapeCodesToSimple(
        "\x1b[42;31mTEXT1 \x1b[32mTEXT2 \x1b[0m");
      expect(ret).toEqual([
        {class: 'ansi42 ansi31', text: 'TEXT1 '},
        {class: 'ansi42 ansi31 ansi32', text: 'TEXT2 '},
      ]);
    });

    it('SGRboth-SGRboth', () => {
      const ret = parseEscapeCodesToSimple(
        "\x1b[42;31mTEXT1 \x1b[43;32mTEXT2 \x1b[0m");
      expect(ret).toEqual([
        {class: 'ansi42 ansi31', text: 'TEXT1 '},
        {class: 'ansi42 ansi31 ansi43 ansi32', text: 'TEXT2 '},
      ]);
    });

    it('SGRboth-256bg', () => {
      const ret = parseEscapeCodesToSimple(
        "\x1b[42;31mTEXT1 \x1b[48;5;34mTEXT2 \x1b[0m");
      expect(ret).toEqual([
        {class: 'ansi42 ansi31', text: 'TEXT1 '},
        {class: 'ansibg-34', text: 'TEXT2 '},
      ]);
    });

    it('SGRboth-256fg', () => {
      const ret = parseEscapeCodesToSimple(
        "\x1b[42;31mTEXT1 \x1b[38;5;226mTEXT2 \x1b[0m");
      expect(ret).toEqual([
        {class: 'ansi42 ansi31', text: 'TEXT1 '},
        {class: 'ansifg-226', text: 'TEXT2 '},
      ]);
    });

    it('SGRboth-256both', () => {
      const ret = parseEscapeCodesToSimple(
        "\x1b[42;31mTEXT1 \x1b[48;5;164;38;5;226mTEXT2 \x1b[0m");
      expect(ret).toEqual([
        {class: 'ansi42 ansi31', text: 'TEXT1 '},
        {class: '', text: 'TEXT2 '},
      ]);
    });

    it('SGRboth-reset0m', () => {
      const ret = parseEscapeCodesToSimple(
        "\x1b[42;31mTEXT1 \x1b[0mTEXT2 \x1b[0m");
      expect(ret).toEqual([
        {class: 'ansi42 ansi31', text: 'TEXT1 '},
        {class: '', text: 'TEXT2 '},
      ]);
    });

    it('SGRboth-resetm', () => {
      const ret = parseEscapeCodesToSimple(
        "\x1b[42;31mTEXT1 \x1b[mTEXT2 \x1b[0m");
      expect(ret).toEqual([
        {class: 'ansi42 ansi31', text: 'TEXT1 '},
        {class: '', text: 'TEXT2 '},
      ]);
    });

    it('256bg-SGRbg', () => {
      const ret = parseEscapeCodesToSimple(
        "\x1b[48;5;34mTEXT1 \x1b[43mTEXT2 \x1b[0m");
      expect(ret).toEqual([
        {class: 'ansibg-34', text: 'TEXT1 '},
        {class: 'ansibg-34 ansi43', text: 'TEXT2 '},
      ]);
    });

    it('256bg-SGRfg', () => {
      const ret = parseEscapeCodesToSimple(
        "\x1b[48;5;34mTEXT1 \x1b[32mTEXT2 \x1b[0m");
      expect(ret).toEqual([
        {class: 'ansibg-34', text: 'TEXT1 '},
        {class: 'ansibg-34 ansi32', text: 'TEXT2 '},
      ]);
    });

    it('256bg-SGRboth', () => {
      const ret = parseEscapeCodesToSimple(
        "\x1b[48;5;34mTEXT1 \x1b[43;32mTEXT2 \x1b[0m");
      expect(ret).toEqual([
        {class: 'ansibg-34', text: 'TEXT1 '},
        {class: 'ansibg-34 ansi43 ansi32', text: 'TEXT2 '},
      ]);
    });

    it('256bg-256bg', () => {
      const ret = parseEscapeCodesToSimple(
        "\x1b[48;5;34mTEXT1 \x1b[48;5;36mTEXT2 \x1b[0m");
      expect(ret).toEqual([
        {class: 'ansibg-34', text: 'TEXT1 '},
        {class: 'ansibg-36', text: 'TEXT2 '},
      ]);
    });

    it('256bg-256fg', () => {
      const ret = parseEscapeCodesToSimple(
        "\x1b[48;5;34mTEXT1 \x1b[38;5;226mTEXT2 \x1b[0m");
      expect(ret).toEqual([
        {class: 'ansibg-34', text: 'TEXT1 '},
        {class: 'ansifg-226', text: 'TEXT2 '},
      ]);
    });

    it('256bg-256both', () => {
      const ret = parseEscapeCodesToSimple(
        "\x1b[48;5;34mTEXT1 \x1b[48;5;164;38;5;226mTEXT2 \x1b[0m");
      expect(ret).toEqual([
        {class: 'ansibg-34', text: 'TEXT1 '},
        {class: '', text: 'TEXT2 '},
      ]);
    });

    it('256bg-reset0m', () => {
      const ret = parseEscapeCodesToSimple(
        "\x1b[48;5;34mTEXT1 \x1b[0mTEXT2 \x1b[0m");
      expect(ret).toEqual([
        {class: 'ansibg-34', text: 'TEXT1 '},
        {class: '', text: 'TEXT2 '},
      ]);
    });

    it('256bg-resetm', () => {
      const ret = parseEscapeCodesToSimple(
        "\x1b[48;5;34mTEXT1 \x1b[mTEXT2 \x1b[0m");
      expect(ret).toEqual([
        {class: 'ansibg-34', text: 'TEXT1 '},
        {class: '', text: 'TEXT2 '},
      ]);
    });

    it('256fg-SGRbg', () => {
      const ret = parseEscapeCodesToSimple(
        "\x1b[38;5;196mTEXT1 \x1b[43mTEXT2 \x1b[0m");
      expect(ret).toEqual([
        {class: 'ansifg-196', text: 'TEXT1 '},
        {class: 'ansifg-196 ansi43', text: 'TEXT2 '},
      ]);
    });

    it('256fg-SGRfg', () => {
      const ret = parseEscapeCodesToSimple(
        "\x1b[38;5;196mTEXT1 \x1b[32mTEXT2 \x1b[0m");
      expect(ret).toEqual([
        {class: 'ansifg-196', text: 'TEXT1 '},
        {class: 'ansifg-196 ansi32', text: 'TEXT2 '},
      ]);
    });

    it('256fg-SGRboth', () => {
      const ret = parseEscapeCodesToSimple(
        "\x1b[38;5;196mTEXT1 \x1b[43;32mTEXT2 \x1b[0m");
      expect(ret).toEqual([
        {class: 'ansifg-196', text: 'TEXT1 '},
        {class: 'ansifg-196 ansi43 ansi32', text: 'TEXT2 '},
      ]);
    });

    it('256fg-256bg', () => {
      const ret = parseEscapeCodesToSimple(
        "\x1b[38;5;196mTEXT1 \x1b[48;5;36mTEXT2 \x1b[0m");
      expect(ret).toEqual([
        {class: 'ansifg-196', text: 'TEXT1 '},
        {class: 'ansibg-36', text: 'TEXT2 '},
      ]);
    });

    it('256fg-256fg', () => {
      const ret = parseEscapeCodesToSimple(
        "\x1b[38;5;196mTEXT1 \x1b[38;5;226mTEXT2 \x1b[0m");
      expect(ret).toEqual([
        {class: 'ansifg-196', text: 'TEXT1 '},
        {class: 'ansifg-226', text: 'TEXT2 '},
      ]);
    });

    it('256fg-256both', () => {
      const ret = parseEscapeCodesToSimple(
        "\x1b[38;5;196mTEXT1 \x1b[48;5;164;38;5;226mTEXT2 \x1b[0m");
      expect(ret).toEqual([
        {class: 'ansifg-196', text: 'TEXT1 '},
        {class: '', text: 'TEXT2 '},
      ]);
    });

    it('256fg-reset0m', () => {
      const ret = parseEscapeCodesToSimple(
        "\x1b[38;5;196mTEXT1 \x1b[0mTEXT2 \x1b[0m");
      expect(ret).toEqual([
        {class: 'ansifg-196', text: 'TEXT1 '},
        {class: '', text: 'TEXT2 '},
      ]);
    });

    it('256fg-resetm', () => {
      const ret = parseEscapeCodesToSimple(
        "\x1b[38;5;196mTEXT1 \x1b[mTEXT2 \x1b[0m");
      expect(ret).toEqual([
        {class: 'ansifg-196', text: 'TEXT1 '},
        {class: '', text: 'TEXT2 '},
      ]);
    });

    it('256both-SGRbg', () => {
      const ret = parseEscapeCodesToSimple(
        "\x1b[48;5;34;38;5;226mTEXT1 \x1b[43mTEXT2 \x1b[0m");
      expect(ret).toEqual([
        {class: '', text: 'TEXT1 '},
        {class: 'ansi43', text: 'TEXT2 '},
      ]);
    });

    it('256both-SGRfg', () => {
      const ret = parseEscapeCodesToSimple(
        "\x1b[48;5;34;38;5;226mTEXT1 \x1b[32mTEXT2 \x1b[0m");
      expect(ret).toEqual([
        {class: '', text: 'TEXT1 '},
        {class: 'ansi32', text: 'TEXT2 '},
      ]);
    });

    it('256both-SGRboth', () => {
      const ret = parseEscapeCodesToSimple(
        "\x1b[48;5;34;38;5;226mTEXT1 \x1b[43;32mTEXT2 \x1b[0m");
      expect(ret).toEqual([
        {class: '', text: 'TEXT1 '},
        {class: 'ansi43 ansi32', text: 'TEXT2 '},
      ]);
    });

    it('256both-256bg', () => {
      const ret = parseEscapeCodesToSimple(
        "\x1b[48;5;34;38;5;226mTEXT1 \x1b[48;5;36mTEXT2 \x1b[0m");
      expect(ret).toEqual([
        {class: '', text: 'TEXT1 '},
        {class: 'ansibg-36', text: 'TEXT2 '},
      ]);
    });

    it('256both-256fg', () => {
      const ret = parseEscapeCodesToSimple(
        "\x1b[48;5;34;38;5;226mTEXT1 \x1b[38;5;228mTEXT2 \x1b[0m");
      expect(ret).toEqual([
        {class: '', text: 'TEXT1 '},
        {class: 'ansifg-228', text: 'TEXT2 '},
      ]);
    });

    it('256both-256both', () => {
      const ret = parseEscapeCodesToSimple(
        "\x1b[48;5;34;38;5;226mTEXT1 \x1b[48;5;164;38;5;228mTEXT2 \x1b[0m");
      expect(ret).toEqual([
        {class: '', text: 'TEXT1 '},
        {class: '', text: 'TEXT2 '},
      ]);
    });

    it('256both-reset0m', () => {
      const ret = parseEscapeCodesToSimple(
        "\x1b[48;5;34;38;5;226mTEXT1 \x1b[0mTEXT2 \x1b[0m");
      expect(ret).toEqual([
        {class: '', text: 'TEXT1 '},
        {class: '', text: 'TEXT2 '},
      ]);
    });

    it('256both-resetm', () => {
      const ret = parseEscapeCodesToSimple(
        "\x1b[48;5;34;38;5;226mTEXT1 \x1b[mTEXT2 \x1b[0m");
      expect(ret).toEqual([
        {class: '', text: 'TEXT1 '},
        {class: '', text: 'TEXT2 '},
      ]);
    });

    it('reset0m-SGRbg', () => {
      const ret = parseEscapeCodesToSimple(
        "\x1b[0mTEXT1 \x1b[43mTEXT2 \x1b[0m");
      expect(ret).toEqual([
        {class: '', text: 'TEXT1 '},
        {class: 'ansi43', text: 'TEXT2 '},
      ]);
    });

    it('reset0m-SGRfg', () => {
      const ret = parseEscapeCodesToSimple(
        "\x1b[0mTEXT1 \x1b[32mTEXT2 \x1b[0m");
      expect(ret).toEqual([
        {class: '', text: 'TEXT1 '},
        {class: 'ansi32', text: 'TEXT2 '},
      ]);
    });

    it('reset0m-SGRboth', () => {
      const ret = parseEscapeCodesToSimple(
        "\x1b[0mTEXT1 \x1b[43;32mTEXT2 \x1b[0m");
      expect(ret).toEqual([
        {class: '', text: 'TEXT1 '},
        {class: 'ansi43 ansi32', text: 'TEXT2 '},
      ]);
    });

    it('reset0m-256bg', () => {
      const ret = parseEscapeCodesToSimple(
        "\x1b[0mTEXT1 \x1b[48;5;36mTEXT2 \x1b[0m");
      expect(ret).toEqual([
        {class: '', text: 'TEXT1 '},
        {class: 'ansibg-36', text: 'TEXT2 '},
      ]);
    });

    it('reset0m-256fg', () => {
      const ret = parseEscapeCodesToSimple(
        "\x1b[0mTEXT1 \x1b[38;5;228mTEXT2 \x1b[0m");
      expect(ret).toEqual([
        {class: '', text: 'TEXT1 '},
        {class: 'ansifg-228', text: 'TEXT2 '},
      ]);
    });

    it('reset0m-256both', () => {
      const ret = parseEscapeCodesToSimple(
        "\x1b[0mTEXT1 \x1b[48;5;164;38;5;228mTEXT2 \x1b[0m");
      expect(ret).toEqual([
        {class: '', text: 'TEXT1 '},
        {class: '', text: 'TEXT2 '},
      ]);
    });

    it('reset0m-reset0m', () => {
      const ret = parseEscapeCodesToSimple(
        "\x1b[0mTEXT1 \x1b[0mTEXT2 \x1b[0m");
      expect(ret).toEqual([
        {class: '', text: 'TEXT1 '},
        {class: '', text: 'TEXT2 '},
      ]);
    });

    it('reset0m-resetm', () => {
      const ret = parseEscapeCodesToSimple(
        "\x1b[0mTEXT1 \x1b[mTEXT2 \x1b[0m");
      expect(ret).toEqual([
        {class: '', text: 'TEXT1 '},
        {class: '', text: 'TEXT2 '},
      ]);
    });

    it('resetm-SGRbg', () => {
      const ret = parseEscapeCodesToSimple(
        "\x1b[mTEXT1 \x1b[43mTEXT2 \x1b[0m");
      expect(ret).toEqual([
        {class: '', text: 'TEXT1 '},
        {class: 'ansi43', text: 'TEXT2 '},
      ]);
    });

    it('resetm-SGRfg', () => {
      const ret = parseEscapeCodesToSimple(
        "\x1b[mTEXT1 \x1b[32mTEXT2 \x1b[0m");
      expect(ret).toEqual([
        {class: '', text: 'TEXT1 '},
        {class: 'ansi32', text: 'TEXT2 '},
      ]);
    });

    it('resetm-SGRboth', () => {
      const ret = parseEscapeCodesToSimple(
        "\x1b[mTEXT1 \x1b[43;32mTEXT2 \x1b[0m");
      expect(ret).toEqual([
        {class: '', text: 'TEXT1 '},
        {class: 'ansi43 ansi32', text: 'TEXT2 '},
      ]);
    });

    it('resetm-256bg', () => {
      const ret = parseEscapeCodesToSimple(
        "\x1b[mTEXT1 \x1b[48;5;36mTEXT2 \x1b[0m");
      expect(ret).toEqual([
        {class: '', text: 'TEXT1 '},
        {class: 'ansibg-36', text: 'TEXT2 '},
      ]);
    });

    it('resetm-256fg', () => {
      const ret = parseEscapeCodesToSimple(
        "\x1b[mTEXT1 \x1b[38;5;228mTEXT2 \x1b[0m");
      expect(ret).toEqual([
        {class: '', text: 'TEXT1 '},
        {class: 'ansifg-228', text: 'TEXT2 '},
      ]);
    });

    it('resetm-256both', () => {
      const ret = parseEscapeCodesToSimple(
        "\x1b[mTEXT1 \x1b[48;5;164;38;5;228mTEXT2 \x1b[0m");
      expect(ret).toEqual([
        {class: '', text: 'TEXT1 '},
        {class: '', text: 'TEXT2 '},
      ]);
    });

    it('resetm-reset0m', () => {
      const ret = parseEscapeCodesToSimple(
        "\x1b[mTEXT1 \x1b[0mTEXT2 \x1b[0m");
      expect(ret).toEqual([
        {class: '', text: 'TEXT1 '},
        {class: '', text: 'TEXT2 '},
      ]);
    });

    it('resetm-resetm', () => {
      const ret = parseEscapeCodesToSimple(
        "\x1b[mTEXT1 \x1b[mTEXT2 \x1b[0m");
      expect(ret).toEqual([
        {class: '', text: 'TEXT1 '},
        {class: '', text: 'TEXT2 '},
      ]);
    });

    it('joint codes', () => {
      const ret = parseEscapeCodesToSimple(
        "\x1b[1;36mDEBUG [plugin]: \x1b[39mLoading plugin karma-jasmine.");
      expect(ret).toEqual([
        {class: 'ansi1 ansi36', text: 'DEBUG [plugin]: '},
        {class: '', text: 'Loading plugin karma-jasmine.'}]);
    });

    it('unsupported modes', () => {
      const val = "\x1b[1A\x1b[2KPhantomJS 1.9.8 (Linux 0.0.0)";
      const ret = parseEscapeCodesToSimple(val);
      expect(ret).toEqual([
        { class: '', text: 'PhantomJS 1.9.8 (Linux 0.0.0)'}]);
    });
  });

  describe('ansi2html', () => {
    it('simple', () => {
      const generated = ansi2html("\x1b[36mDEBUG [plugin]: \x1b[39mLoading plugin karma-jasmine.");
      const component = render(<>{generated}</>);
      expect(component.asFragment()).toMatchSnapshot();
    });
  });

  describe('generateStyleElement', () => {
    it('simple', () => {
      const component = render(generateStyleElement("pre.log"));
      expect(component.asFragment()).toMatchSnapshot();
    });
  });
});
