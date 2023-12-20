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

import './LogSearchField.scss'
import {Ref, useState} from "react";
import {FaChevronDown, FaChevronUp, FaSearch} from "react-icons/fa";
import {VscCaseSensitive, VscRegex} from "react-icons/vsc";

export type LogSearchButtonProps = {
  currentResult: number;
  totalResults: number;
  onSearchInputChanged: (text: string, caseSensitive: boolean, useRegex: boolean) => void;
  onPrevClicked: () => void;
  onNextClicked: () => void;
  inputRef: Ref<HTMLInputElement>;
};

export const LogSearchField = ({currentResult, totalResults,
                                onSearchInputChanged, onPrevClicked, onNextClicked,
                                inputRef}: LogSearchButtonProps) => {
  const [searchText, setSearchText] = useState<string>('');
  const [hasFocus, setHasFocus] = useState<boolean>(false);
  const [isCaseSensitive, setIsCaseSensitive] = useState<boolean>(true);
  const [useRegex, setUseRegex] = useState<boolean>(false);

  const onSearchTextChanged = (text: string) => {
    setSearchText(text);
    onSearchInputChanged(text, isCaseSensitive, useRegex);
  };

  const onCaseInsensitiveToggled = () => {
    const newValue = !isCaseSensitive;
    setIsCaseSensitive(newValue);
    onSearchInputChanged(searchText, newValue, useRegex);
  }

  const onUseRegexToggled = () => {
    const newValue = !useRegex;
    setUseRegex(newValue);
    onSearchInputChanged(searchText, isCaseSensitive, newValue);
  }

  const optionButtonClass = (optionName: string, isToggled: boolean) => {
    return [
      'bb-log-search-field-options',
      `bb-log-search-field-options-${optionName}`,
      `bb-log-search-field-options-${isToggled ? 'toggled' : 'untoggled'}`,
    ].join(' ');
  };
  const renderOptions = () => (
    <>
      <button
        className={optionButtonClass('case', isCaseSensitive)}
        onClick={onCaseInsensitiveToggled}>
        <VscCaseSensitive />
      </button>
      <button
        className={optionButtonClass('regex', useRegex)}
        onClick={onUseRegexToggled}>
        <VscRegex />
      </button>
    </>
  );

  const renderSearchNav = () => (
    <div className="bb-log-search-field-nav">
      <span className="bb-log-search-field-result-count">{currentResult}/{totalResults}</span>
      <button className="bb-log-search-field-nav-button" onClick={onPrevClicked}>
        <FaChevronUp/>
      </button>
      <button className="bb-log-search-field-nav-button" onClick={onNextClicked}>
        <FaChevronDown/>
      </button>
    </div>
  );

  const onKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (hasFocus && e.key === "Enter") {
      e.preventDefault();
      onNextClicked();
    }
  }

  const shouldRenderOptionals = (hasFocus || searchText !== '');

  return (
    <form role="search" className="bb-log-search-field">
      <FaSearch className="bb-log-search-field-icon"/>
      {shouldRenderOptionals ? renderOptions() : <></>}
      <input className="bb-log-search-field-text" type="text" value={searchText}
             ref={inputRef}
             onFocus={() => setHasFocus(true)} onBlur={() => setHasFocus(false)}
             onChange={e => onSearchTextChanged(e.target.value)}
             onKeyDown={e => onKeyDown(e)}
             placeholder="Search log"/>
      {shouldRenderOptionals ? renderSearchNav() : <></>}
    </form>
  );
}
