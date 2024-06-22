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
  //
  // Note that when there are many key-value pairs waiting for replies from the server side, nth
  // element might appear in an unexpected position. First requests replies can take longer than
  // replies to the following values, so they get their values first. In this case, nth element
  // will actually be later than expected, because preceding values have not arrived yet.
  // The nth element is always the same when there is only one key-value pair or when all the
  // information has already been acquired from the server.
  getNthOrNull(index: number): DataType | null {
    for (const parentId of this.sortedParentIds) {
      const childCollection = this.byParentId.get(parentId);
      if (childCollection === undefined) {
        continue;
      }
      if (index < childCollection.array.length) {
        return childCollection.array[index];
      }
      index -= childCollection.array.length;
    }
    return null;
  }

  getAll(): DataType[] {
    const all: DataType[] = [];
    for (const parentId of this.sortedParentIds) {
      const childCollection = this.byParentId.get(parentId);
      if (childCollection === undefined) {
        continue;
      }
      all.push(...childCollection.array);
    }
    return all;
  }

  getNthOfParentOrNull(parentId: string, index: number): DataType | null {
    const childCollection = this.byParentId.get(parentId);
    if (childCollection === undefined) {
      return null;
    }
    if (index >= childCollection.array.length) {
      return null;
    }
    return childCollection.array[index];
  }

  getParentCollectionOrEmpty(parentId: string): DataCollection<DataType> {
    const childCollection = this.byParentId.get(parentId);
    if (childCollection === undefined) {
      return new DataCollection<DataType>();
    }
    return childCollection;
  }
}
