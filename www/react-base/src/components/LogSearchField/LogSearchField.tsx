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
import {useState} from "react";
import {FaChevronDown, FaChevronUp, FaSearch} from "react-icons/fa";

export type LogSearchButtonProps = {
  currentResult: number;
  totalResults: number;
  onTextChanged: (text: string) => void;
  onPrevClicked: () => void;
  onNextClicked: () => void;
};

export const LogSearchField = ({currentResult, totalResults,
                                onTextChanged, onPrevClicked, onNextClicked}: LogSearchButtonProps) => {
  const [searchText, setSearchText] = useState<string>('');
  const [hasFocus, setHasFocus] = useState<boolean>(false);

  const onSearchTextChanged = (text: string) => {
    setSearchText(text);
    onTextChanged(text);
  };

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

  return (
    <form role="search" className="bb-log-search-field">
      <FaSearch className="bb-log-search-field-icon"/>
      <input className="bb-log-search-field-text" type="text" value={searchText}
             onFocus={() => setHasFocus(true)} onBlur={() => setHasFocus(false)}
             onChange={e => onSearchTextChanged(e.target.value)}
             onKeyDown={e => onKeyDown(e)}
             placeholder="Search log"/>
      {(hasFocus || searchText !== '') ? renderSearchNav() : <></>}
    </form>
  );
}
