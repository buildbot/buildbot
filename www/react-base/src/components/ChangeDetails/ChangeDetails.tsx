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

import './ChangeDetails.scss';
import {Change} from "../../data/classes/Change";
import {dateFormat, durationFromNowFormat, useCurrentTime} from "../../util/Moment";
import {useState} from "react";
import ArrowExpander from "../ArrowExpander/ArrowExpander";
import {OverlayTrigger, Popover, Table} from "react-bootstrap";
import {parseChangeAuthorNameAndEmail} from "../../util/Properties";
import ChangeUserAvatar from "../ChangeUserAvatar/ChangeUserAvatar";

type ChangeDetailsProps = {
  change: Change;
  compact: boolean;
  showDetails: boolean;
  setShowDetails: (show: boolean) => void;
}

const ChangeDetails = ({change, compact, showDetails, setShowDetails}: ChangeDetailsProps) => {
  const now = useCurrentTime();
  const [showProps, setShowProps] = useState(false);

  const renderChangeDetails = () => (
    <div className="anim-changedetails">
      <Table striped size="sm">
        <tbody>
          { change.category !== null
            ? <tr>
              <td>Category</td>
              <td>{change.category}</td>
            </tr>
            : <></>
          }
          <tr>
            <td>Author</td>
            <td>{change.author}</td>
          </tr>
          <tr>
            <td>Date</td>
            <td>{dateFormat(change.when_timestamp)} ({durationFromNowFormat(change.when_timestamp, now)})</td>
          </tr>
          <tr>
            <td>Codebase</td>
            <td>{change.codebase}</td>
          </tr>
          { change.repository !== null
            ? <tr>
              <td>Repository</td>
              <td>{change.repository}</td>
            </tr>
            : <></>
          }
          { change.branch !== null
            ? <tr>
              <td>Branch</td>
              <td>{change.branch}</td>
            </tr>
            : <></>
          }
          <tr>
            <td>Revision</td>
            <td>{change.revision}</td>
          </tr>
          <tr>
            <td>Properties</td>
            <td>
              <ArrowExpander isExpanded={showProps} setIsExpanded={setShowProps}/>
              { showProps
                ? <pre className="changedetails-properties">{JSON.stringify(change.properties)}</pre>
                : <></>
              }
            </td>
          </tr>
        </tbody>
      </Table>
      <h5>Comment</h5>
      <pre>{change.comments}</pre>
      <h5>Changed files</h5>
      {change.files.length === 0
        ? <p>No files</p>
        : <ul>{change.files.map(file => (<li key={file}>{file}</li>))}</ul>
      }
    </div>
  );

  const [changeAuthorName, changeEmail] = parseChangeAuthorNameAndEmail(change.author);

  const popoverWithText = (id: string, text: string) => {
    return (
      <Popover id={"bb-popover-change-details-" + id}>
        <Popover.Content>
          {text}
        </Popover.Content>
      </Popover>
    );
  }

  return (
    <div className="changedetails">
      <div className="changedetails-heading" onClick={() => setShowDetails(!showDetails)}>
        { !compact
          ? <ChangeUserAvatar name={changeAuthorName} email={changeEmail} showName={false}/>
          : <></>
        }
        <OverlayTrigger placement="top"
                        overlay={popoverWithText("comments-" + change.id, change.comments)}>
          {
            change.revlink !== null
            ? <a href={change.revlink}>{change.comments.split("\n")[0]}</a>
            : <span>{change.comments.split("\n")[0]}</span>
          }
        </OverlayTrigger>
        { !compact
          ? <OverlayTrigger placement="top"
                            overlay={popoverWithText("date-" + change.id,
                              dateFormat(change.when_timestamp))}>
              <span>({durationFromNowFormat(change.when_timestamp, now)})</span>
            </OverlayTrigger>
          : <></>
        }
        <ArrowExpander isExpanded={showDetails}/>
      </div>
      {showDetails ? renderChangeDetails() : <></>}
    </div>
  );
}

export default ChangeDetails;
