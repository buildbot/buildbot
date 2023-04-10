/*
  This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0. If a copy of the
  MPL was not distributed with this file, You can obtain one at https://mozilla.org/MPL/2.0/.

  Copyright Buildbot Team Members
*/

import {BaseClass} from "./classes/BaseClass";
import {BasicDataMultiCollection} from "./BasicDataMultiCollection";
import {DataPropertiesCollection} from "./DataPropertiesCollection";

export class DataMultiPropertiesCollection<ParentDataType extends BaseClass>
  extends BasicDataMultiCollection<ParentDataType, DataPropertiesCollection> {

  getParentCollectionOrEmpty(parentId: string): DataPropertiesCollection {
    const collection = this.byParentId.get(parentId);
    if (collection === undefined) {
      return new DataPropertiesCollection();
    }
    return collection;
  }
}
