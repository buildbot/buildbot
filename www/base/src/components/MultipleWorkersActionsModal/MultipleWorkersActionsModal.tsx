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

import './MultipleWorkersActionsModal.scss'
import {observer} from "mobx-react";
import {useState, useRef} from "react";
import {Button, Modal} from "react-bootstrap";
import {Worker} from "buildbot-data-js";
import Select, { ActionMeta, MultiValue, InputActionMeta, SelectInstance, components, ControlProps } from 'react-select';
import { BsRegex, BsCheckAll } from "react-icons/bs";

type MultipleWorkersActionsModalProps = {
  workers: Worker[];
  preselectedWorkers: Worker[];
  onClose: () => void;
}

interface SelectOption {
  readonly value: Worker,
  readonly label: string,
}

const workerToSelectOption = (worker: Worker): SelectOption => {
  return { value: worker, label: worker.name }
}

interface FilterControlPanelProps<OptionType> extends ControlProps<OptionType, true> {
  toggleRegexSearch: boolean;
  handleToggleClick: (e: React.MouseEvent<HTMLDivElement>) => void;
  handleSelectAllClick: (e: React.MouseEvent<HTMLDivElement>) => void;
  selectRef: React.RefObject<SelectInstance<OptionType, true>>;
}

const FilterControlPanel = <OptionType,>(props: FilterControlPanelProps<OptionType>) => {
  const { toggleRegexSearch, handleToggleClick, handleSelectAllClick, selectRef } = props;

  const [ isHoveredRegexSearch, setIsHoveredRegexSearch ] = useState(false);

  const [isHoveredSelectAll, setIsHoveredSelectAll] = useState(false);
  const [isActiveSelectAll, setIsActiveSelectAll] = useState(false);

  return (
    <components.Control {...props}>
      <div className="bb-workers-actions-modal-control-container">
        {Array.isArray(props.children) && props.children[0]}
        <div
          className={`icon-button ${isHoveredSelectAll ? 'hovered' : ''} ${isActiveSelectAll ? 'active' : ''}`}
          onMouseEnter={() => setIsHoveredSelectAll(true)}
          onMouseLeave={() => {
            setIsHoveredSelectAll(false);
            setIsActiveSelectAll(false);
          }}
          onMouseDown={(e) => {
            setIsActiveSelectAll(true);
            handleSelectAllClick(e);
            if (selectRef && selectRef.current) {
              setTimeout(() => {
                selectRef?.current?.focus();
              }, 0);
            }
          }}
          onMouseUp={() => setIsActiveSelectAll(false)}
          title="Select All Filtered"
        >
          <BsCheckAll size={20} />
        </div>

        <div
          className={`icon-button ${isHoveredRegexSearch ? 'hovered' : ''} ${toggleRegexSearch ? 'active' : ''}`}
          onMouseEnter={() => setIsHoveredRegexSearch(true)}
          onMouseLeave={() => setIsHoveredRegexSearch(false)}
          onMouseDown={(e) => {
            handleToggleClick(e);
            if (selectRef?.current) {
              setTimeout(() => {
                selectRef.current?.focus();
              }, 0);
            }
          }}
          title="Toggle Regex Search"
        >
          <BsRegex size={20} />
        </div>
        {Array.isArray(props.children) && props.children.slice(1)}
      </div>
    </components.Control>
  );
};

export const MultipleWorkersActionsModal = observer(({workers, preselectedWorkers, onClose}: MultipleWorkersActionsModalProps) => {
  if (workers.length === 1) {
    preselectedWorkers = [...workers];
  }

  const [errors, setErrors] = useState<string|null>(null);
  const [reasonText, setReasonText] = useState<string>("");
  const [selectedWorkers, setSelectedWorkers] = useState<Worker[]>(preselectedWorkers);
  const [menuIsOpen, setMenuIsOpen] = useState<boolean>();
  const [toggleRegexSearch, setToggleRegexSearch] = useState(false);
  const selectRef = useRef<SelectInstance<SelectOption, true> | null>(null);

  const stopDisabled = selectedWorkers.length <= 0 || selectedWorkers.every(w => w.connected_to.length === 0)
  const pauseDisabled = selectedWorkers.length <= 0 || selectedWorkers.every(w => w.paused)
  const unpauseDisabled = selectedWorkers.length <= 0 || selectedWorkers.every(w => !w.paused)

  const doAction = async (method: string) => {
    if (selectedWorkers.length <= 0) {
      setErrors("No worker selected for action");
      return
    }
    setErrors(null);
    const results = await Promise.allSettled(selectedWorkers.map(w => w.control(method, {reason: reasonText})));
    const rejectedActions = results.filter(r => r.status === "rejected")
    if (rejectedActions.length > 0) {
      setErrors(rejectedActions.map(r => (r as PromiseRejectedResult).reason).join("\n"));
    }
    else {
      onClose();
    }
  }

  const onInputChange = (
    inputValue: string,
    { action, prevInputValue }: InputActionMeta
  ) => {
    if (action === 'input-change') {
      return inputValue;
    }
    if (action === 'menu-close') {
      setMenuIsOpen(prevInputValue ? true : undefined);
    }
    return prevInputValue;
  };

  const handleToggleClick = (e: React.MouseEvent) => {
    e.preventDefault();
    setToggleRegexSearch((prev) => !prev);
  };

  const handleSelectAllClick = (e: React.MouseEvent) => {
    e.preventDefault();

    const currentInputValue = selectRef.current?.inputRef?.value || '';
    const filteredWorkers = workers.filter(worker => {
      const option = workerToSelectOption(worker);
      return filterOption({ data: option }, currentInputValue);
    });

    setSelectedWorkers(prevSelectedWorkers => {
      const existingWorkerNames = new Set(prevSelectedWorkers.map(w => w.name));

      const newWorkers = filteredWorkers.filter(w => !existingWorkerNames.has(w.name));

      return [...prevSelectedWorkers, ...newWorkers];
    });
    refocusSelect();
  };

  const filterOption = (option: { data: SelectOption }, inputValue: string) => {
    if (toggleRegexSearch) {
      try {
        const regex = new RegExp(inputValue, 'i');
        return regex.test(option.data.label);
      } catch (e) {
        return false;
      }
    } else {
      return option.data.label.toLowerCase().includes(inputValue.toLowerCase());
    }
  };

  const refocusSelect = () => {
    if (selectRef.current) {
      setTimeout(() => {
        selectRef.current?.focus();
      }, 0);
    }
  };

  return (
    <Modal size="lg" show={true} onHide={() => onClose()}>
      <Modal.Header closeButton>
        <Modal.Title>Worker actions for {workers.length === 1 ? workers[0].name : "..."}</Modal.Title>
      </Modal.Header>
      <Modal.Body>
        <div className="form-horizontal">
          {
            errors === null
              ? <></>
              : <div ng-show="error" className="alert alert-danger">{errors}</div>
          }
          {workers.length !== 1 ?
            <Select<SelectOption, true>
              ref={selectRef}
              isMulti
              closeMenuOnSelect={false}
              autoFocus
              value={selectedWorkers.map(workerToSelectOption)}
              onChange={(newValue: MultiValue<SelectOption>, _actionMeta: ActionMeta<SelectOption>) => {
                setSelectedWorkers(newValue.map(v => v.value));
                refocusSelect();
              }}
              onInputChange={onInputChange}
              options={workers.map(workerToSelectOption)}
              filterOption={filterOption}
              components={{
                Control: (controlProps) => (
                  <FilterControlPanel
                    {...controlProps}
                    toggleRegexSearch={toggleRegexSearch}
                    handleToggleClick={handleToggleClick}
                    handleSelectAllClick={handleSelectAllClick}
                    selectRef={selectRef}
                  />
                )
              }}
            />
            : <></>
          }
          <label htmlFor="reason" className="control-label col-sm-2">Reason</label>
          <div className="col-sm-10">
            <textarea rows={15} value={reasonText} onChange={e => setReasonText(e.target.value)}
                      className="form-control"/>
          </div>
        </div>
      </Modal.Body>
      <Modal.Footer>
        <Button variant="default" onClick={() => onClose()}>Cancel</Button>
        <Button variant="primary" disabled={stopDisabled} onClick={async () => await doAction('stop')}>
          Graceful Shutdown
        </Button>
        <Button variant="primary" disabled={stopDisabled} onClick={async () => await doAction('kill')}>
          Force Shutdown
        </Button>
        <Button variant="primary" disabled={pauseDisabled} onClick={async () => await doAction('pause')}>
          Pause
        </Button>
        <Button variant="primary" disabled={unpauseDisabled} onClick={async () => await doAction('unpause')}>
          Unpause
        </Button>
      </Modal.Footer>
    </Modal>
  )
});
