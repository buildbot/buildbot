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

import {Builder} from 'buildbot-data-js';
import {pushIntoMapOfArrays} from 'buildbot-ui';

export type TagTreeItem = {
  builders: Builder[];
  tag: string;
  childItems: TagTreeItem[];
};

export type TagItemConfig = {
  tag: string;
  colSpan: number;
};

export type TagLineConfig = TagItemConfig[];

export function buildTagTree(builders: Builder[]) {
  const buildersByTags = new Map<string, Builder[]>();
  for (const builder of builders) {
    if (builder.tags === null) {
      continue;
    }
    for (const tag of builder.tags) {
      pushIntoMapOfArrays(buildersByTags, tag, builder);
    }
  }

  type TagInfo = {
    tag: string;
    builders: Builder[];
  };

  const undecidedTags: TagInfo[] = [];
  for (const [tag, tagBuilders] of buildersByTags) {
    if (tagBuilders.length < builders.length) {
      undecidedTags.push({tag: tag, builders: tagBuilders});
    }
  }

  // sort the tags to first look at tags with the larger number of builders
  // @FIXME maybe this is not the best method to find the best groups
  undecidedTags.sort((a, b) => b.builders.length - a.builders.length);

  const tagItems: TagTreeItem[] = [];
  const builderIdToTag = new Map<number, string>();

  // pick the tags one by one, by making sure we make non-overalaping groups
  for (const tagInfo of undecidedTags) {
    let excluded = false;
    for (const builder of tagInfo.builders) {
      if (builderIdToTag.has(builder.builderid)) {
        excluded = true;
        break;
      }
    }
    if (!excluded) {
      for (const builder of tagInfo.builders) {
        builderIdToTag.set(builder.builderid, tagInfo.tag);
      }
      tagItems.push({tag: tagInfo.tag, builders: tagInfo.builders, childItems: []});
    }
  }

  // some builders do not have tags, we put them in another group
  const remainingBuilders = [];
  for (const builder of builders) {
    if (!builderIdToTag.has(builder.builderid)) {
      remainingBuilders.push(builder);
    }
  }

  if (remainingBuilders.length) {
    tagItems.push({tag: '', builders: remainingBuilders, childItems: []});
  }

  // if there is more than one tag in this line, we need to recurse
  if (tagItems.length > 1) {
    for (const tagItem of tagItems) {
      tagItem.childItems = buildTagTree(tagItem.builders);
    }
  }
  return tagItems;
}

// Sorts and groups builders together by their tags.
export function sortBuildersByTags(builders: Builder[]): [Builder[], TagLineConfig[]] {
  // we call recursive function, which finds non-overlapping groups
  const tagLineItems = buildTagTree(builders);

  // we get a tree of builders grouped by tags
  // we now need to flatten the tree, in order to build several lines of tags
  // (each line is representing a depth in the tag tree)
  // we walk the tree left to right and build the list of builders in the tree order, and the tag_lines
  // in the tree, there are groups of remaining builders, which could not be grouped together,
  // those have the empty tag ''
  const tagLineConfigAtDepth = new Map<number, TagLineConfig>();

  const resultBuilders: Builder[] = [];

  const setTagLine = (depth: number, tag: string, colSpan: number) => {
    const lineConfig = tagLineConfigAtDepth.get(depth);
    if (lineConfig === undefined) {
      tagLineConfigAtDepth.set(depth, [{tag: tag, colSpan: colSpan}]);
      return;
    }

    // Attempt to merge identical tags
    const lastItem = lineConfig[lineConfig.length - 1];
    if (lastItem.tag === tag) {
      lastItem.colSpan += colSpan;
      return;
    }
    lineConfig.push({tag: tag, colSpan: colSpan});
  };

  const walkItemTree = (tagItem: TagTreeItem, depth: number) => {
    setTagLine(depth, tagItem.tag, tagItem.builders.length);
    if (tagItem.childItems.length === 0) {
      // this is the leaf of the tree, sort by buildername, and add them to the
      // list of sorted builders
      tagItem.builders.sort((a, b) => a.name.localeCompare(b.name));

      resultBuilders.push(...tagItem.builders);

      for (let i = 1; i <= 100; i++) {
        // set the remaining depth of the tree to the same colspan
        // (we hardcode the maximum depth for now :/ )
        setTagLine(depth + i, '', tagItem.builders.length);
      }
      return;
    }
    tagItem.childItems.map((item) => walkItemTree(item, depth + 1));
  };

  for (const tagItem of tagLineItems) {
    walkItemTree(tagItem, 0);
  }

  const resultTagLineConfigs: TagLineConfig[] = [];

  for (const tagLineItems of tagLineConfigAtDepth.values()) {
    if (tagLineItems.length === 1 && tagLineItems[0].tag === '') {
      continue;
    }
    resultTagLineConfigs.push(tagLineItems);
  }
  return [resultBuilders, resultTagLineConfigs];
}
