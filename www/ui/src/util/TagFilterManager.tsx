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

import './TagFilterManager.scss'
import {Badge, OverlayTrigger, Popover} from "react-bootstrap";
import {FaQuestionCircle} from "react-icons/fa";
import {URLSearchParamsInit, useSearchParams} from "react-router-dom";

export const computeToggledTag3Way = (tags: string[], tag: string) => {
  if (tag === '') {
    return tags;
  }

  if (tag.indexOf('+') === 0) {
    tag = tag.slice(1);
  }
  if (tag.indexOf('-') === 0) {
    tag = tag.slice(1);
  }

  const i = tags.indexOf(tag);
  const iplus = tags.indexOf(`+${tag}`);
  const iminus = tags.indexOf(`-${tag}`);

  const newTags = [...tags];
  if ((i < 0) && (iplus < 0) && (iminus < 0)) {
    newTags.push(`+${tag}`);
  } else if (iplus >= 0) {
    newTags.splice(iplus, 1);
    newTags.push(`-${tag}`);
  } else if (iminus >= 0) {
    newTags.splice(iminus, 1);
    newTags.push(tag);
  } else {
    newTags.splice(i, 1);
  }
  return newTags;
}

export const computeToggledTagOnOff = (tags: string[], tag: string) => {
  if (tag === '') {
    return tags;
  }

  const i = tags.indexOf(tag);

  const newTags = [...tags];
  if (i < 0) {
    newTags.push(tag);
  } else {
    newTags.splice(i, 1);
  }
  return newTags;
}

export enum TagFilterManagerTagMode {
  Toggle3Way,
  ToggleOnOff
}

export class TagFilterManager {
  tags: string[];
  searchParams: URLSearchParams;
  setSearchParams: (nextInit: URLSearchParamsInit) => void;
  mode: TagFilterManagerTagMode;

  constructor(searchParams: URLSearchParams,
              setSearchParams: (nextInit: URLSearchParamsInit) => void,
              urlParamName: string,
              mode: TagFilterManagerTagMode) {
    this.tags = searchParams.getAll(urlParamName);
    this.searchParams = searchParams;
    this.setSearchParams = setSearchParams;
    this.mode = mode;
  }

  shouldShowByTags(tags: string[]) {
    const pluses = this.tags.filter(tag => tag.indexOf("+") === 0);
    const minuses = this.tags.filter(tag => tag.indexOf("-") === 0);

    // First enforce that we have no tag marked '-'
    for (const tag of minuses) {
      if (tags.indexOf(tag.slice(1)) >= 0) {
        return false;
      }
    }

    // if only minuses or no filter
    if (this.tags.length === minuses.length) {
      return true;
    }

    // Then enforce that we have all the tags marked '+'
    for (const tag of pluses) {
      if (tags.indexOf(tag.slice(1)) < 0) {
        return false;
      }
    }

    // Then enforce that we have at least one of the tag (marked '+' or not)
    for (let tag of this.tags) {
      if (tag.indexOf("+") === 0) {
        tag = tag.slice(1);
      }
      if (tags.indexOf(tag) >= 0) {
        return true;
      }
    }
    return false;
  }

  private setTags(tags: string[]) {
    const newParams = new URLSearchParams([...this.searchParams.entries()]);
    newParams.delete("tags");
    for (const tag of tags) {
      newParams.append("tags", tag);
    }
    this.setSearchParams(newParams);
  }

  private toggleTag(tag: string) {
    this.setTags(this.computeToggledTag(tag));
  };

  private computeToggledTag(tag: string) {
    switch (this.mode) {
      case TagFilterManagerTagMode.Toggle3Way:
        return computeToggledTag3Way(this.tags, tag);
      case TagFilterManagerTagMode.ToggleOnOff:
        return computeToggledTagOnOff(this.tags, tag);
    }
  }

  private isTagFiltered(tag: string) {
    return (
      (this.tags.length === 0) ||
      (this.tags.indexOf(tag) >= 0) ||
      (this.tags.indexOf(`+${tag}`) >= 0) ||
      (this.tags.indexOf(`-${tag}`) >= 0)
    );
  }

  getFiltersHelpElement() {
    const tagHelpPopover = (
      <Popover id="bb-tag-filter-manager-help-popover"
               style={{display: "block", minWidth: "600px", left:"-300px", top: "30px"}}>
        <Popover.Title as="h5">Tags filtering</Popover.Title>
        <Popover.Content>
          <p><b>
            <pre>+{"{tag}"}</pre></b>all tags with '+' must be present in the builder tags</p>
          <p><b>
            <pre>-{"{tag}"}</pre></b>no tags with '-' must be present in the builder tags</p>
          <p><b>
            <pre>{"{tag}"}</pre></b>at least one of the filtered tag should be present</p>
          <p>url bar is updated with you filter configuration, so you can bookmark your filters!</p>
        </Popover.Content>
      </Popover>
    );

    const tagHelpElement = (
      <OverlayTrigger trigger="click" placement="bottom" overlay={tagHelpPopover} rootClose={true}>
        <FaQuestionCircle style={{position: "relative"}} className="clickable"/>
      </OverlayTrigger>
    );
    return tagHelpElement;
  }

  getEnabledFiltersElements() {
    const enabledTagsElements: JSX.Element[] = [];
    if (this.tags.length === 0) {
      enabledTagsElements.push((
        <span>Tags</span>
      ));
    }
    if (this.tags.length < 5) {
      for (const tag of this.tags) {
        enabledTagsElements.push((
          <>
            <Badge variant="success"
                   onClick={() => this.toggleTag(tag)} className="clickable">{tag}</Badge>
            &nbsp;
          </>
        ));
      }
    } else {
      enabledTagsElements.push((
        <Badge variant="success">{this.tags.length} tags</Badge>
      ));
    }
    if (this.tags.length > 0) {
      enabledTagsElements.push((
        <Badge variant="danger" onClick={() => this.setTags([])} className="clickable">x</Badge>
      ));
    }

    return enabledTagsElements;
  }

  getElementsForTags(tags: string[]) {
    return tags.map(tag => {
      return (
        <span key={tag}>
          <span onClick={() => this.toggleTag(tag)}
                className={"bb-tag-filter-manager-tag clickable " +
                  (this.isTagFiltered(tag) ? 'bb-tag-filter-manager-tag-filtered': '')}>
              {tag}
            </span>
          &nbsp;
        </span>
      );
    });
  }
}

export const useTagFilterManager = (urlParamName: string, mode?: TagFilterManagerTagMode) => {
  if (mode === undefined) {
    mode = TagFilterManagerTagMode.Toggle3Way;
  }
  const [searchParams, setSearchParams] = useSearchParams();
  return new TagFilterManager(searchParams, setSearchParams, urlParamName, mode);
}
