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
  ansi2html,
  generateStyleElement,
  parseAnsiSgr,
  parseEscapeCodesToClasses,
} from "./AnsiEscapeCodes";
import renderer from "react-test-renderer";

describe('AnsiEscapeCodes', () => {

  describe('parseAnsiSgr', () => {
    const runTest = (ansi: string, expectedEntry: string, expectedClasses: string[]) => {
      expect(parseAnsiSgr(ansi)).toEqual([expectedEntry, expectedClasses]);
    };

    it("test_ansi0m", () => runTest("mfoo", "foo", []));

    it("test ansi1m", () => runTest("33mfoo", "foo", ["33"]));

    it("test ansi2m", () => runTest("1;33mfoo", "foo", ["1", "33"]));

    it("test ansi5m", () => runTest("1;2;3;4;33mfoo", "foo", ["1", "2", "3", "4", "33"]));

    it("test ansi_notm", () => runTest("33xfoo", "foo", []));

    it("test ansi_invalid", () => runTest("<>foo", "\x1b[<>foo", []));

    it("test ansi_invalid_start_by_semicolon", () => runTest(";3m", "\x1b[;3m", []));
  });

  describe('parseEscapeCodes', () => {
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

    it('256 colors', () => {
      const ret = parseEscapeCodesToSimple(
        "\x1b[48;5;71mDEBUG \x1b[38;5;72m[plugin]: \x1b[39mLoading plugin karma-jasmine.");
      expect(ret).toEqual([
        {class: 'ansibg-71', text: 'DEBUG '},
        {class: 'ansifg-72', text: '[plugin]: '},
        {class: '', text: 'Loading plugin karma-jasmine.'}]);
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
      const component = renderer.create(<>{generated}</>);
      expect(component.toJSON()).toMatchSnapshot();
    });
  });

  describe('generateStyleElement', () => {
    it('simple', () => {
      const component = renderer.create(generateStyleElement("pre.log"));
      expect(component.toJSON()).toMatchSnapshot();
    });
  });
});
