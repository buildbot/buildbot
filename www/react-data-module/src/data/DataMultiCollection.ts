/*
  This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0. If a copy of the
  MPL was not distributed with this file, You can obtain one at https://mozilla.org/MPL/2.0/.

  Copyright Buildbot Team Members
*/

import {BaseClass} from "./classes/BaseClass";
import {DataCollection} from "./DataCollection";
import {BasicDataMultiCollection} from "./BasicDataMultiCollection";

export class DataMultiCollection<ParentDataType extends BaseClass,
    DataType extends BaseClass> extends BasicDataMultiCollection<ParentDataType, DataCollection<DataType>> {

  getRelated<ChildDataType extends BaseClass>(
    callback: (child: DataType) => DataCollection<ChildDataType>) {
    return new DataMultiCollection<DataType, ChildDataType>(this.accessor, null, this.byParentId,
      null, callback);
  }

  // Acquires nth element across all collections tracked by this multi collection. The iteration
  // order is in ascending order of parent IDs.
  getNthOrNull(index: number): DataType | null {
    for (const parentId of this.sortedParentIds) {
      const parent = this.byParentId.get(parentId);
      if (parent === undefined) {
        continue;
      }
      if (index < parent.array.length) {
        return parent.array[index];
      }
      index -= parent.array.length;
    }
    return null;
  }

  getAll(): DataType[] {
    const all: DataType[] = [];
    for (const parentId of this.sortedParentIds) {
      const parent = this.byParentId.get(parentId);
      if (parent === undefined) {
        continue;
      }
      all.push(...parent.array);
    }
    return all;
  }

  getNthOfParentOrNull(parentId: string, index: number): DataType | null {
    const collection = this.byParentId.get(parentId);
    if (collection === undefined) {
      return null;
    }
    if (index >= collection.array.length) {
      return null;
    }
    return collection.array[index];
  }

  getParentCollectionOrEmpty(parentId: string): DataCollection<DataType> {
    const collection = this.byParentId.get(parentId);
    if (collection === undefined) {
      return new DataCollection<DataType>();
    }
    return collection;
  }
}
