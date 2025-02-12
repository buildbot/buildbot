/*
  This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0. If a copy of the
  MPL was not distributed with this file, You can obtain one at https://mozilla.org/MPL/2.0/.

  Copyright Buildbot Team Members
*/

import {action, makeObservable, observable} from "mobx";
import {BaseClass} from "./BaseClass";
import {IDataDescriptor} from "./DataDescriptor";
import {IDataAccessor} from "../DataAccessor";

export class CodebaseCommit extends BaseClass {
  @observable commitid!: number;
  @observable codebaseid!: number;
  @observable author!: string;
  @observable committer!: string|null;
  @observable comments!: string;
  @observable when_timestamp!: number;
  @observable revision!: string;
  @observable parent_commitid!: number|null;

  constructor(accessor: IDataAccessor, endpoint: string, object: any) {
    super(accessor, endpoint, String(object.commitid));
    this.update(object);
    makeObservable(this);
  }

  @action update(object: any) {
    this.commitid = object.commitid;
    this.codebaseid = object.codebaseid;
    this.author = object.author;
    this.committer = object.committer;
    this.comments = object.comments;
    this.when_timestamp = object.when_timestamp;
    this.revision = object.revision;
    this.parent_commitid = object.parent_commitid;
  }

  toObject() {
    return {
      commitid: this.commitid,
      codebaseid: this.codebaseid,
      author: this.author,
      committer: this.committer,
      comments: this.comments,
      when_timestamp: this.when_timestamp,
      revision: this.revision,
      parent_commitid: this.parent_commitid,
    };
  }
}

export class CodebaseCommitDescriptor implements IDataDescriptor<CodebaseCommit> {
  restArrayField = "commits";
  fieldId: string = "commitid";

  parse(accessor: IDataAccessor, endpoint: string, object: any) {
    return new CodebaseCommit(accessor, endpoint, object);
  }
}

export const codebaseCommitDescriptor = new CodebaseCommitDescriptor();
