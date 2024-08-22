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
/*
  The code is based on the react-window project: https://github.com/bvaughn/react-window
  version  1.8.9 (6ff5694ac810617515acf74401ba68fe2951133b)

  The MIT License (MIT)

  Copyright (c) 2018 Brian Vaughn

  Permission is hereby granted, free of charge, to any person obtaining a copy
  of this software and associated documentation files (the "Software"), to deal
  in the Software without restriction, including without limitation the rights
  to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
  copies of the Software, and to permit persons to whom the Software is
  furnished to do so, subject to the following conditions:

  The above copyright notice and this permission notice shall be included in all
  copies or substantial portions of the Software.

  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
  IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
  FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
  AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
  LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
  OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
  SOFTWARE.
*/

import {beforeEach, describe, expect, it, vi} from "vitest";
import React, {createRef, memo} from 'react';
import {createRoot} from 'react-dom/client';
import renderer from "react-test-renderer";
import {Simulate} from 'react-dom/test-utils';
import {FixedSizeList, FixedSizeListProps} from './FixedSizeList';
import * as domHelpers from './domHelpers';
import Mock = vi.Mock;

const simulateScroll = (instance: FixedSizeList<any>, scrollOffset: number, direction = 'vertical') => {
  if (direction === 'horizontal') {
    instance._outerRef!.scrollLeft = scrollOffset;
  } else {
    instance._outerRef!.scrollTop = scrollOffset;
  }
  Simulate.scroll(instance._outerRef!);
};

const findScrollContainer = (rendered: any) => rendered.root.children[0].children[0];

async function waitForAnimationFrame() {
  const p = new Promise<void>((resolve, reject) => {
    window.requestAnimationFrame(() => {
      resolve();
    });
  });
  await p;
}

async function sleepMs(ms: number) {
  var promise = new Promise((r) => setTimeout(r, ms));
  await promise;
}

async function renderWithReactDom(children: React.ReactNode) {
  const instance = createRoot(document.createElement('div'));
  instance.render(children);
  await waitForAnimationFrame();
  await new Promise((resolve) => setTimeout(resolve, 0));
  await vi.runAllTimersAsync();
  await waitForAnimationFrame();
}


describe('FixedSizeList', () => {
  let itemRenderer: Mock;
  let getScrollbarSize: Mock;
  let onItemsRendered: Mock;
  let defaultProps: FixedSizeListProps<any>;

  let mockedScrollHeight = Number.MAX_SAFE_INTEGER;
  let mockedScrollWidth = Number.MAX_SAFE_INTEGER;

  beforeEach(() => {
    vi.useFakeTimers({ toFake: ['nextTick'] });

    mockedScrollHeight = Number.MAX_SAFE_INTEGER;
    mockedScrollWidth = Number.MAX_SAFE_INTEGER;

    // JSdom does not do actual layout and so doesn't return meaningful values here.
    // For the purposes of our tests though, we can mock out semi-meaningful values.
    // This mock is required for e.g. "onScroll" tests to work properly.
    Object.defineProperties(HTMLDivElement.prototype, {
      clientWidth: {
        configurable: true,
        get: function() {
          return parseInt(this.style.width, 10) || 0;
        },
      },
      clientHeight: {
        configurable: true,
        get: function() {
          return parseInt(this.style.height, 10) || 0;
        },
      },
      scrollHeight: {
        configurable: true,
        get: () => mockedScrollHeight,
      },
      scrollWidth: {
        configurable: true,
        get: () => mockedScrollWidth,
      },
    });

    // Mock the DOM helper util for testing purposes.
    getScrollbarSize = vi.spyOn(domHelpers, "getScrollbarSize");
    getScrollbarSize.mockImplementation(() => 0);

    onItemsRendered = vi.fn();


    itemRenderer = vi.fn(({ style, ...rest }) => (
      <div style={style}>{JSON.stringify(rest, null, 2)}</div>
    ));

    // @ts-ignore
    defaultProps = {
      children: memo((props) => itemRenderer(props)),
      height: 100,
      itemCount: 100,
      itemSize: 25,
      onItemsRendered,
      width: 50,
    };
  });

  it('should render an empty list', () => {
    renderer.create(<FixedSizeList {...defaultProps} itemCount={0} />);
    expect(itemRenderer).not.toHaveBeenCalled();
    expect(onItemsRendered).not.toHaveBeenCalled();
  });

  it('should render a list of rows', () => {
    renderer.create(<FixedSizeList {...defaultProps} />);
    expect(itemRenderer).toHaveBeenCalledTimes(6);
    expect(onItemsRendered.mock.calls).toMatchSnapshot();
  });

  describe('scrollbar handling', () => {
    it('should set width to "100%" for vertical lists to avoid unnecessary horizontal scrollbar',
        async () => {
      const innerRef = createRef<HTMLDivElement>();
      await renderWithReactDom(<FixedSizeList {...defaultProps} innerRef={innerRef} />);

      const style = innerRef.current!.style;
      expect(style.width).toBe('100%');
      expect(style.height).toBe('2500px');
    });
  });

  describe('style caching', () => {
    it('should cache styles while scrolling to avoid breaking pure sCU for items', () => {
      const ref = createRef<FixedSizeList<any>>();
      renderer.create(<FixedSizeList {...defaultProps} ref={ref}/>);
      // Scroll a few times.
      // Each time, make sure to render item 3.
      ref.current!.scrollToItem(1, 'start');
      ref.current!.scrollToItem(2, 'start');
      ref.current!.scrollToItem(3, 'start');
      // Find all of the times item 3 was rendered.
      // If we are caching props correctly, it should only be once.
      expect(
        itemRenderer.mock.calls.filter(([params]) => params.index === 3)
      ).toHaveLength(1);
    });
  });

  it('changing itemSize updates the rendered items', () => {
    const rendered = renderer.create(<FixedSizeList {...defaultProps} />);
    rendered.update(<FixedSizeList {...defaultProps} itemSize={50} />);
    expect(onItemsRendered.mock.calls).toMatchSnapshot();
  });

  it('changing itemSize updates the rendered items and busts the style cache', () => {
    const rendered = renderer.create(
      <FixedSizeList {...defaultProps} />
    );
    const oldStyle = itemRenderer.mock.calls[0][0].style;
    itemRenderer.mockClear();
    rendered.update(<FixedSizeList {...defaultProps} itemSize={50} />);
    expect(itemRenderer).toHaveBeenCalled();
    const newStyle = itemRenderer.mock.calls[0][0].style;
    expect(oldStyle).not.toBe(newStyle);
  });

  it('should support momentum scrolling on iOS devices', () => {
    const rendered = renderer.create(<FixedSizeList {...defaultProps} />);
    expect((rendered.toJSON() as any).props.style.WebkitOverflowScrolling).toBe('touch');
  });

  it('should disable pointer events while scrolling', () => {
    const ref = createRef<FixedSizeList<any>>();
    const rendered = renderer.create(
      <FixedSizeList {...defaultProps} ref={ref}/>
    );
    const scrollContainer = findScrollContainer(rendered);
    expect(scrollContainer.props.style.pointerEvents).toBe(undefined);
    ref.current!.setState({ isScrolling: true });
    expect(scrollContainer.props.style.pointerEvents).toBe('none');
  });

  describe('style overrides', () => {
    it('should support className prop', () => {
      const rendered = renderer.create(
        <FixedSizeList {...defaultProps} className="custom" />
      );
      expect((rendered.toJSON() as any).props.className).toBe('custom');
    });

    it('should support style prop', () => {
      const rendered = renderer.create(
        <FixedSizeList {...defaultProps} style={{ backgroundColor: 'red' }} />
      );
      expect((rendered.toJSON() as any).props.style.backgroundColor).toBe('red');
    });
  });

  describe('direction', () => {
    it('should set the appropriate CSS direction style', () => {
      const rendered = renderer.create(<FixedSizeList {...defaultProps} direction="ltr" />);
      expect((rendered.toJSON() as any).props.style.direction).toBe('ltr');
      rendered.update(<FixedSizeList {...defaultProps} direction="rtl" />);
      expect((rendered.toJSON() as any).props.style.direction).toBe('rtl');
    });

    it('should position items correctly', () => {
      const rendered = renderer.create(<FixedSizeList {...defaultProps} direction="ltr" />);

      let params = itemRenderer.mock.calls[0][0];
      expect(params.index).toBe(0);
      let style = params.style;
      expect(style.left).toBe(0);
      expect(style.right).toBeUndefined();

      itemRenderer.mockClear();

      rendered.update(<FixedSizeList {...defaultProps} direction="rtl" />);

      params = itemRenderer.mock.calls[0][0];
      expect(params.index).toBe(0);
      style = params.style;
      expect(style.left).toBeUndefined();
      expect(style.right).toBe(0);
    });
  });

  describe('overscanCount', () => {
    it('should require a minimum of 1 overscan to support tabbing', () => {
      renderer.create(
        <FixedSizeList
          {...defaultProps}
          initialScrollOffset={50}
          overscanCount={0}
        />
      );
      expect(onItemsRendered.mock.calls).toMatchSnapshot();
    });

    it('should overscan in the direction being scrolled', async () => {
      const ref = createRef<FixedSizeList<any>>();
      await renderWithReactDom(
        <FixedSizeList
          {...defaultProps}
          initialScrollOffset={50}
          overscanCount={2}
          ref={ref}
        />
      );

      // Simulate scrolling (rather than using scrollTo) to test isScrolling state.
      simulateScroll(ref.current!, 100);
      await waitForAnimationFrame();

      simulateScroll(ref.current!, 50);
      await waitForAnimationFrame();

      expect(onItemsRendered.mock.calls).toMatchSnapshot();
    });

    it('should overscan in both directions when not scrolling', () => {
      renderer.create(<FixedSizeList {...defaultProps} initialScrollOffset={50} />);
      expect(onItemsRendered.mock.calls).toMatchSnapshot();
    });

    it('should accommodate a custom overscan', () => {
      renderer.create(
        <FixedSizeList
          {...defaultProps}
          initialScrollOffset={100}
          overscanCount={3}
        />
      );
      expect(onItemsRendered.mock.calls).toMatchSnapshot();
    });

    it('should not scan past the beginning of the list', () => {
      renderer.create(<FixedSizeList {...defaultProps} initialScrollOffset={0} />);
      expect(onItemsRendered.mock.calls).toMatchSnapshot();
    });

    it('should not scan past the end of the list', () => {
      renderer.create(
        <FixedSizeList
          {...defaultProps}
          itemCount={10}
          initialScrollOffset={150}
        />
      );
      expect(onItemsRendered.mock.calls).toMatchSnapshot();
    });
  });

  describe('useIsScrolling', () => {
    it('should not pass an isScrolling param to children unless requested', () => {
      renderer.create(<FixedSizeList {...defaultProps} />);
      expect(itemRenderer.mock.calls[0][0].isScrolling).toBe(undefined);
    });

    /*it('should pass an isScrolling param to children if requested', async () => {
      // Use ReactDOM renderer so the container ref and "onScroll" work correctly.
      const ref = createRef<FixedSizeList<any>>();
      await renderWithReactDom(
        <FixedSizeList {...defaultProps} useIsScrolling ref={ref}/>
      );

      expect(itemRenderer.mock.calls[0][0].isScrolling).toBe(false);
      itemRenderer.mockClear();
      simulateScroll(ref.current!, 100);

      vi.runAllTimers();

      expect(itemRenderer.mock.calls[0][0].isScrolling).toBe(true);
      itemRenderer.mockClear();

      await waitForAnimationFrame();
      vi.runAllTimers();

      expect(itemRenderer.mock.calls[0][0].isScrolling).toBe(false);
    });*/

    it('should not re-render children unnecessarily if isScrolling param is not used', async () => {
      // Use ReactDOM renderer so the container ref and "onScroll" work correctly.
      const ref = createRef<FixedSizeList<any>>();
      await renderWithReactDom(<FixedSizeList {...defaultProps} overscanCount={1} ref={ref}/>);

      simulateScroll(ref.current!, 100);
      itemRenderer.mockClear();
      vi.runAllTimers();
      expect(itemRenderer).not.toHaveBeenCalled();
    });
  });

  describe('scrollTo method', () => {
    it('should not report isScrolling', async () => {
      // Use ReactDOM renderer so the container ref and "onScroll" work correctly.
      const ref = createRef<FixedSizeList<any>>();
      await renderWithReactDom(<FixedSizeList {...defaultProps} useIsScrolling ref={ref}/>);

      itemRenderer.mockClear();

      ref.current!.scrollTo(100);
      await waitForAnimationFrame();

      expect(itemRenderer.mock.calls[0][0].isScrolling).toBe(false);
    });

    it('should ignore values less than zero', async () => {
      const onScroll = vi.fn();
      const ref = createRef<FixedSizeList<any>>();
      await renderWithReactDom(<FixedSizeList {...defaultProps} onScroll={onScroll} ref={ref}/>);

      ref.current!.scrollTo(100);
      await waitForAnimationFrame();

      onScroll.mockClear();

      ref.current!.scrollTo(-1);
      await waitForAnimationFrame();

      expect(onScroll.mock.calls[0][0].scrollOffset).toBe(0);
    });
  });

  describe('scrollToItem method', () => {
    it('should not set invalid offsets when the list contains few items', () => {
      const onScroll = vi.fn();
      const ref = createRef<FixedSizeList<any>>();
      renderer.create(
        <FixedSizeList {...defaultProps} itemCount={3} onScroll={onScroll} ref={ref}/>
      );
      expect(onItemsRendered).toMatchSnapshot();
      onItemsRendered.mockClear();
      ref.current!.scrollToItem(0);
      expect(onItemsRendered).not.toHaveBeenCalled();
    });

    it('should scroll to the correct item for align = "auto"', () => {
      const ref = createRef<FixedSizeList<any>>();
      renderer.create(<FixedSizeList {...defaultProps} ref={ref}/>);
      // Scroll down enough to show item 10 at the bottom.
      ref.current!.scrollToItem(10, 'auto');
      // No need to scroll again; item 9 is already visible.
      // Because there's no scrolling, it won't call onItemsRendered.
      ref.current!.scrollToItem(9, 'auto');
      // Scroll up enough to show item 2 at the top.
      ref.current!.scrollToItem(2, 'auto');
      expect(onItemsRendered.mock.calls).toMatchSnapshot();
    });

    it('scroll with align = "auto" should work with partially-visible items', () => {
      const ref = createRef<FixedSizeList<any>>();
      renderer.create(
        // Create list where items don't fit exactly into container.
        // The container has space for 3 1/3 items.
        <FixedSizeList {...defaultProps} itemSize={30} ref={ref}/>
      );
      // Scroll down enough to show item 10 at the bottom.
      // Should show 4 items: 3 full and one partial at the beginning
      ref.current!.scrollToItem(10, 'auto');
      // No need to scroll again; item 9 is already visible.
      // Because there's no scrolling, it won't call onItemsRendered.
      ref.current!.scrollToItem(9, 'auto');
      // Scroll to near the end. #96 will be shown as partial.
      ref.current!.scrollToItem(99, 'auto');
      // Scroll back to show #96 fully. This will cause #99 to be shown as a
      // partial. Because #96 was already shown previously as a partial, all
      // props of the onItemsRendered will be the same. This means that even
      // though a scroll happened in the DOM, onItemsRendered won't be called.
      ref.current!.scrollToItem(96, 'auto');
      // Scroll forward again. Because item #99 was already shown partially,
      // all props of the onItemsRendered will be the same.
      ref.current!.scrollToItem(99, 'auto');
      // Scroll to the second item. A partial fifth item should
      // be shown after it.
      ref.current!.scrollToItem(1, 'auto');
      // Scroll to the first item. Now the fourth item should be a partial.
      ref.current!.scrollToItem(0, 'auto');
      expect(onItemsRendered.mock.calls).toMatchSnapshot();
    });

    it('scroll with align = "auto" should work with very small lists and partial items', () => {
      const ref = createRef<FixedSizeList<any>>();
      renderer.create(
        // Create list with only two items, one of which will be shown as a partial.
        <FixedSizeList {...defaultProps} itemSize={60} itemCount={2} ref={ref}/>
      );
      // Show the second item fully. The first item should be a partial.
      ref.current!.scrollToItem(1, 'auto');
      // Go back to the first item. The second should be a partial again.
      ref.current!.scrollToItem(0, 'auto');
      // None of the scrollToItem calls above should actually cause a scroll,
      // so there will only be one snapshot.
      expect(onItemsRendered.mock.calls).toMatchSnapshot();
    });

    it('should scroll to the correct item for align = "start"', () => {
      const ref = createRef<FixedSizeList<any>>();
      renderer.create(<FixedSizeList {...defaultProps} ref={ref}/>);

      // Scroll down enough to show item 10 at the top.
      ref.current!.scrollToItem(10, 'start');
      // Scroll back up so that item 9 is at the top.
      // Overscroll direction wil change too.
      ref.current!.scrollToItem(9, 'start');
      // Item 99 can't align at the top because there aren't enough items.
      // Scroll down as far as possible though.
      // Overscroll direction wil change again.
      ref.current!.scrollToItem(99, 'start');
      expect(onItemsRendered.mock.calls).toMatchSnapshot();
    });

    it('should scroll to the correct item for align = "end"', () => {
      const ref = createRef<FixedSizeList<any>>();
      renderer.create(
        <FixedSizeList {...defaultProps} ref={ref}/>
      );
      // Scroll down enough to show item 10 at the bottom.
      ref.current!.scrollToItem(10, 'end');
      // Scroll back up so that item 9 is at the bottom.
      // Overscroll direction wil change too.
      ref.current!.scrollToItem(9, 'end');
      // Item 1 can't align at the bottom because it's too close to the beginning.
      // Scroll up as far as possible though.
      // Overscroll direction wil change again.
      ref.current!.scrollToItem(1, 'end');
      expect(onItemsRendered.mock.calls).toMatchSnapshot();
    });

    it('should scroll to the correct item for align = "center"', () => {
      const ref = createRef<FixedSizeList<any>>();
      renderer.create(<FixedSizeList {...defaultProps} ref={ref}/>);

      // Scroll down enough to show item 10 in the middle.
      ref.current!.scrollToItem(10, 'center');
      // Scroll back up so that item 9 is in the middle.
      // Overscroll direction wil change too.
      ref.current!.scrollToItem(9, 'center');
      // Item 1 can't align in the middle because it's too close to the beginning.
      // Scroll up as far as possible though.
      // Overscroll direction wil change again.
      ref.current!.scrollToItem(1, 'center');
      // Item 99 can't align in the middle because it's too close to the end.
      // Scroll down as far as possible though.
      // Overscroll direction wil change again.
      ref.current!.scrollToItem(99, 'center');
      expect(onItemsRendered.mock.calls).toMatchSnapshot();
    });

    it('should scroll to the correct item for align = "smart"', () => {
      const ref = createRef<FixedSizeList<any>>();
      renderer.create(<FixedSizeList {...defaultProps} ref={ref}/>);
      // Scroll down enough to show item 10 in the middle.
      ref.current!.scrollToItem(10, 'smart');
      // Scrolldn't scroll at all because it's close enough.
      ref.current!.scrollToItem(9, 'smart');
      // Should scroll but not center because it's close enough.
      ref.current!.scrollToItem(6, 'smart');
      // Item 1 can't align in the middle because it's too close to the beginning.
      // Scroll up as far as possible though.
      ref.current!.scrollToItem(1, 'smart');
      // Item 99 can't align in the middle because it's too close to the end.
      // Scroll down as far as possible though.
      ref.current!.scrollToItem(99, 'smart');
      // This shouldn't scroll at all because it's close enough.
      ref.current!.scrollToItem(95, 'smart');
      ref.current!.scrollToItem(99, 'smart');
      // This should scroll with the 'auto' behavior because it's within a screen.
      ref.current!.scrollToItem(94, 'smart');
      ref.current!.scrollToItem(99, 'smart');
      // This should scroll with the 'center' behavior because it's too far.
      ref.current!.scrollToItem(90, 'smart');
      ref.current!.scrollToItem(99, 'smart');
      expect(onItemsRendered.mock.calls).toMatchSnapshot();
    });

    it('should not report isScrolling', async () => {
      // Use ReactDOM renderer so the container ref and "onScroll" work correctly.
      const ref = createRef<FixedSizeList<any>>();
      await renderWithReactDom(<FixedSizeList {...defaultProps} useIsScrolling ref={ref}/>);

      itemRenderer.mockClear();
      ref.current!.scrollToItem(15);
      await waitForAnimationFrame();

      expect(itemRenderer.mock.calls[itemRenderer.mock.calls.length - 1][0].isScrolling).toBe(false);
    });

    it('should ignore indexes less than zero', async () => {
      const ref = createRef<FixedSizeList<any>>();
      await renderWithReactDom(<FixedSizeList {...defaultProps} ref={ref}/>);

      ref.current!.scrollToItem(20);
      await waitForAnimationFrame();

      onItemsRendered.mockClear();
      ref.current!.scrollToItem(-1);
      await waitForAnimationFrame();

      expect(onItemsRendered.mock.calls).toMatchSnapshot();
    });

    it('should ignore indexes greater than itemCount', async () => {
      const ref = createRef<FixedSizeList<any>>();
      await renderWithReactDom(<FixedSizeList {...defaultProps} ref={ref}/>);

      onItemsRendered.mockClear();
      ref.current!.scrollToItem(defaultProps.itemCount * 2);
      await waitForAnimationFrame();

      expect(onItemsRendered.mock.calls).toMatchSnapshot();
    });

    it('should account for scrollbar size', async () => {
      getScrollbarSize.mockImplementation(() => 20);

      const ref = createRef<FixedSizeList<any>>();
      await renderWithReactDom(<FixedSizeList {...defaultProps} ref={ref} />);

      // Mimic the vertical list not being horizontally scrollable.
      // To be clear, this would be typical.
      mockedScrollWidth = 0;

      ref.current!.scrollToItem(20, 'auto');
      await waitForAnimationFrame();

      // Now mimic the vertical list not being horizontally scrollable,
      // and make sure the list accounts for the horizontal scrollbar height.
      mockedScrollWidth = Number.MAX_SAFE_INTEGER;

      ref.current!.scrollToItem(20, 'auto');
      await waitForAnimationFrame();

      expect(onItemsRendered.mock.calls).toMatchSnapshot();
    });
  });

  // onItemsRendered is pretty well covered by other snapshot tests
  describe('onScroll', () => {
    it('should call onScroll after mount', () => {
      const onScroll = vi.fn();
      renderer.create(
        <FixedSizeList {...defaultProps} onScroll={onScroll} />
      );
      expect(onScroll.mock.calls).toMatchSnapshot();
    });

    it('should call onScroll when scroll position changes', () => {
      const onScroll = vi.fn();
      const ref = createRef<FixedSizeList<any>>();
      renderer.create(<FixedSizeList {...defaultProps} onScroll={onScroll} ref={ref}/>);

      ref.current!.scrollTo(100);
      ref.current!.scrollTo(0);
      expect(onScroll.mock.calls).toMatchSnapshot();
    });

    it('should distinguish between "onScroll" events and scrollTo() calls', async () => {
      const onScroll = vi.fn();
      // Use ReactDOM renderer so the container ref and "onScroll" event work correctly.
      const ref = createRef<FixedSizeList<any>>();

      await renderWithReactDom(<FixedSizeList {...defaultProps} onScroll={onScroll} ref={ref}/>);

      onScroll.mockClear();
      ref.current!.scrollTo(100);
      await waitForAnimationFrame();

      expect(onScroll.mock.calls[0][0].scrollUpdateWasRequested).toBe(true);

      onScroll.mockClear();
      simulateScroll(ref.current!, 200);
      await waitForAnimationFrame();

      expect(onScroll.mock.calls[0][0].scrollUpdateWasRequested).toBe(false);
    });

    it('scrolling should report partial items correctly in onItemsRendered', async () => {
      // Use ReactDOM renderer so the container ref works correctly.
      const ref = createRef<FixedSizeList<any>>();
      await renderWithReactDom(
        <FixedSizeList {...defaultProps} initialScrollOffset={20} ref={ref}/>
      );

      // Scroll 2 items fwd, but thanks to the initialScrollOffset, we should
      // still be showing partials on both ends.
      simulateScroll(ref.current!, 70);
      await waitForAnimationFrame();

      // Scroll a little fwd to cause partials to be hidden
      simulateScroll(ref.current!, 75);
      await waitForAnimationFrame();

      // Scroll backwards to show partials again
      simulateScroll(ref.current!, 70);
      await waitForAnimationFrame();

      // Scroll near the end so that the last item is shown
      // as a partial.
      simulateScroll(ref.current!, 96 * 25 - 5);
      await waitForAnimationFrame();

      // Scroll to the end. No partials.
      simulateScroll(ref.current!, 96 * 25);
      await waitForAnimationFrame();

      // Verify that backwards scrolling near the end works OK.
      simulateScroll(ref.current!, 96 * 25 - 5);
      await waitForAnimationFrame();

      expect(onItemsRendered.mock.calls).toMatchSnapshot();
    });
  });

  describe('itemKey', () => {
    it('should be used', () => {
      const itemKey = vi.fn(index => index);
      renderer.create(
        <FixedSizeList {...defaultProps} itemCount={3} itemKey={itemKey} />
      );
      expect(itemKey).toHaveBeenCalledTimes(3);
      expect(itemKey.mock.calls[0][0]).toBe(0);
      expect(itemKey.mock.calls[1][0]).toBe(1);
      expect(itemKey.mock.calls[2][0]).toBe(2);
    });

    it('should allow items to be moved within the collection without causing caching problems', () => {
      const keyMap = ['0', '1', '2'];
      const keyMapItemRenderer = vi.fn(({ index, style }) => (
        <div style={style}>{keyMap[index]}</div>
      ));

      const ref = createRef<FixedSizeList<any>>();

      const itemKey = vi.fn(index => keyMap[index]);
      renderer.create(
        <FixedSizeList {...defaultProps} itemCount={3} itemKey={itemKey} ref={ref}>
          {memo((props) => keyMapItemRenderer(props))}
        </FixedSizeList>
      );
      expect(itemKey).toHaveBeenCalledTimes(3);
      itemKey.mockClear();

      expect(keyMapItemRenderer).toHaveBeenCalledTimes(3);
      keyMapItemRenderer.mockClear();

      // Simulate swapping the first and last items.
      keyMap[0] = '2';
      keyMap[2] = '0';

      ref.current!.forceUpdate();

      // Our key getter should be called again for each key.
      // Since we've modified the map, the first and last key will swap.
      expect(itemKey).toHaveBeenCalledTimes(3);

      // The first and third item have swapped place,
      // So they should have been re-rendered,
      // But the second item should not.
      expect(keyMapItemRenderer).toHaveBeenCalledTimes(2);
      expect(keyMapItemRenderer.mock.calls[0][0].index).toBe(0);
      expect(keyMapItemRenderer.mock.calls[1][0].index).toBe(2);
    });

    it('should receive a data value if itemData is provided', () => {
      const itemKey = vi.fn(index => index);
      const itemData = {};
      renderer.create(
        <FixedSizeList
          {...defaultProps}
          itemData={itemData}
          itemKey={itemKey}
        />
      );
      expect(itemKey).toHaveBeenCalled();
      expect(
        itemKey.mock.calls.filter((value: [any, any]) => value[1] === itemData)
      ).toHaveLength(itemKey.mock.calls.length);
    });
  });

  describe('refs', () => {
    it('should pass through innerRef and outerRef ref functions', async () => {
      const innerRef = vi.fn();
      const outerRef = vi.fn();
      await renderWithReactDom(
        <FixedSizeList
          {...defaultProps}
          innerRef={innerRef}
          outerRef={outerRef}
        />
      );
      expect(innerRef).toHaveBeenCalled();
      expect(innerRef.mock.calls[0][0]).toBeInstanceOf(HTMLDivElement);
      expect(outerRef).toHaveBeenCalled();
      expect(outerRef.mock.calls[0][0]).toBeInstanceOf(HTMLDivElement);
    });

    it('should pass through innerRef and outerRef createRef objects', async () => {
      const innerRef = createRef<HTMLDivElement>();
      const outerRef = createRef<HTMLDivElement>();

      await renderWithReactDom(
        <FixedSizeList
          {...defaultProps}
          innerRef={innerRef}
          outerRef={outerRef}
        />,
      );
      expect(innerRef.current).toBeInstanceOf(HTMLDivElement);
      expect(outerRef.current).toBeInstanceOf(HTMLDivElement);
    });
  });

  describe('custom element types', () => {
    it('should use a custom innerElementType if specified', () => {
      const rendered = renderer.create(
        <FixedSizeList {...defaultProps} innerElementType="section" />
      );
      expect(rendered.root.findByType('section')).toBeDefined();
    });

    it('should use a custom outerElementType if specified', () => {
      const rendered = renderer.create(
        <FixedSizeList {...defaultProps} outerElementType="section" />
      );
      expect(rendered.root.findByType('section')).toBeDefined();
    });

    /*it('should support spreading additional, arbitrary props, e.g. id', () => {
      const container = document.createElement('div');
      const instance = createRoot(container);
      instance.render(
        <FixedSizeList
          {...defaultProps}
          innerElementType={forwardRef<HTMLDivElement>((props, ref) => (
            <div ref={ref} id="inner" {...props} />
          ))}
          outerElementType={forwardRef<HTMLDivElement>((props, ref) => (
            <div ref={ref} id="outer" {...props} />
          ))}
        />,
      );
      expect((container.firstChild as HTMLElement).id).toBe('outer');
      expect((container.firstChild!.firstChild! as HTMLElement).id).toBe('inner');
    });*/
  });

  describe('itemData', () => {
    it('should pass itemData to item renderers as a "data" prop', () => {
      const itemData = {};
      renderer.create(<FixedSizeList {...defaultProps} itemData={itemData} />);
      expect(itemRenderer).toHaveBeenCalled();
      expect(
        itemRenderer.mock.calls.filter(([params]) => params.data === itemData)
      ).toHaveLength(itemRenderer.mock.calls.length);
    });

    it('should re-render items if itemData changes', () => {
      const itemData = {};
      const rendered = renderer.create(<FixedSizeList {...defaultProps} itemData={itemData} />);
      expect(itemRenderer).toHaveBeenCalled();
      itemRenderer.mockClear();

      // Re-rendering should not affect pure sCU children:
      rendered.update(<FixedSizeList {...defaultProps} itemData={itemData} />);
      expect(itemRenderer).not.toHaveBeenCalled();

      // Re-rendering with new itemData should re-render children:
      const newItemData = {};
      rendered.update(<FixedSizeList {...defaultProps} itemData={newItemData} />);
      expect(itemRenderer).toHaveBeenCalled();
      expect(
        itemRenderer.mock.calls.filter(
          ([params]) => params.data === newItemData
        )
      ).toHaveLength(itemRenderer.mock.calls.length);
    });
  });
});
