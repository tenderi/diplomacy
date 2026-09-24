/**
 * Track I1: the inline map opens a full-viewport viewer that can zoom and pan.
 *
 * jsdom reports 0 for `clientWidth`/`clientHeight` and never loads images, so the
 * "fit to viewport" path degrades to 1:1 here (asserted below, so the fallback is
 * covered rather than merely tolerated). The zoom/pan maths is exercised through the
 * rendered transform, which is the thing that actually moves the image.
 */
import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, fireEvent, within, cleanup } from '@testing-library/react'
import MapViewer from './MapViewer'

// `globals` is off in vite.config.ts, so Testing Library cannot register its automatic
// per-test cleanup -- without this every test would see the previous test's DOM. Same
// reason and same fix as GameView.test.tsx.
afterEach(() => cleanup())

// jsdom implements neither `PointerEvent` nor `Element.setPointerCapture` (verified: both
// are `undefined`). Without a polyfill, `fireEvent.pointerMove` falls back to a bare `Event`
// that silently drops `pointerId`/`clientX`/`clientY` -- so every pointer test would compute
// `NaN` deltas and appear to prove the component ignores drags. Polyfilling is what makes
// the pan/pinch assertions below mean anything.
class FakePointerEvent extends MouseEvent {
  pointerId: number
  constructor(type: string, props: PointerEventInit = {}) {
    super(type, props)
    this.pointerId = props.pointerId ?? 0
  }
}
;(globalThis as unknown as { PointerEvent: typeof PointerEvent }).PointerEvent =
  FakePointerEvent as unknown as typeof PointerEvent

const SRC = 'http://api.test/games/1/map?t=1'

/** The transformed <img> inside the open dialog. */
function viewerImage(): HTMLImageElement {
  const dialog = screen.getByRole('dialog')
  return within(dialog).getAllByRole('img')[0] as HTMLImageElement
}

function scaleOf(el: HTMLElement): number {
  const m = /scale\(([\d.]+)\)/.exec(el.style.transform)
  return m ? Number(m[1]) : NaN
}

function translateOf(el: HTMLElement): { x: number; y: number } {
  // The first translate() is the -50%/-50% centring; the second is the pan offset.
  const m = /translate\((-?[\d.]+)px, (-?[\d.]+)px\)/.exec(el.style.transform)
  return m ? { x: Number(m[1]), y: Number(m[2]) } : { x: NaN, y: NaN }
}

function open() {
  render(<MapViewer src={SRC} alt="Board — S1901M" />)
  fireEvent.click(screen.getByRole('button', { name: /enlarge map/i }))
}

describe('MapViewer', () => {
  it('shows the map inline with no dialog until the trigger is clicked', () => {
    render(<MapViewer src={SRC} alt="Board — S1901M" />)
    expect(screen.getByAltText('Board — S1901M')).toHaveAttribute('src', SRC)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('exposes the trigger as a named button so the map is reachable by keyboard', () => {
    render(<MapViewer src={SRC} alt="Board — S1901M" />)
    const trigger = screen.getByRole('button', { name: 'Enlarge map: Board — S1901M' })
    expect(trigger).toHaveAttribute('type', 'button')
  })

  it('opens a labelled modal dialog showing the same image', () => {
    open()
    const dialog = screen.getByRole('dialog')
    expect(dialog).toHaveAttribute('aria-modal', 'true')
    expect(dialog).toHaveAccessibleName('Map viewer: Board — S1901M')
    expect(viewerImage()).toHaveAttribute('src', SRC)
  })

  it('moves focus into the dialog on open', () => {
    open()
    expect(screen.getByRole('dialog')).toHaveFocus()
  })

  it('closes on Escape', () => {
    open()
    fireEvent.keyDown(window, { key: 'Escape' })
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('closes via the close button', () => {
    open()
    fireEvent.click(screen.getByRole('button', { name: 'Close map viewer' }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('zooms in and out with the toolbar buttons and reports the level', () => {
    open()
    expect(screen.getByText('100%')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Zoom in' }))
    expect(scaleOf(viewerImage())).toBeCloseTo(1.25, 5)
    expect(screen.getByText('125%')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Zoom out' }))
    expect(scaleOf(viewerImage())).toBeCloseTo(1, 5)
  })

  it('zooms with the wheel: up magnifies, down shrinks', () => {
    open()
    const viewport = screen.getByTestId('map-viewport')

    fireEvent.wheel(viewport, { deltaY: -100, clientX: 0, clientY: 0 })
    expect(scaleOf(viewerImage())).toBeCloseTo(1.25, 5)

    fireEvent.wheel(viewport, { deltaY: 100, clientX: 0, clientY: 0 })
    expect(scaleOf(viewerImage())).toBeCloseTo(1, 5)
  })

  it('clamps zoom to its bounds instead of running away', () => {
    open()
    const zoomIn = screen.getByRole('button', { name: 'Zoom in' })
    for (let i = 0; i < 40; i++) fireEvent.click(zoomIn)
    expect(scaleOf(viewerImage())).toBeLessThanOrEqual(6)
    expect(scaleOf(viewerImage())).toBeCloseTo(6, 5)

    const zoomOut = screen.getByRole('button', { name: 'Zoom out' })
    for (let i = 0; i < 80; i++) fireEvent.click(zoomOut)
    expect(scaleOf(viewerImage())).toBeCloseTo(0.1, 5)
  })

  it('keeps the point under the cursor fixed when wheel-zooming off-centre', () => {
    open()
    const viewport = screen.getByTestId('map-viewport')
    // Viewport centre is (0,0) in jsdom (getBoundingClientRect is all zeroes), so a
    // cursor at (100, 50) is 100px right and 50px below the transform origin.
    fireEvent.wheel(viewport, { deltaY: -100, clientX: 100, clientY: 50 })

    const img = viewerImage()
    expect(scaleOf(img)).toBeCloseTo(1.25, 5)
    // x' = px - (px - x) * ratio = 100 - 100 * 1.25 = -25; y' = 50 - 50 * 1.25 = -12.5
    expect(translateOf(img).x).toBeCloseTo(-25, 5)
    expect(translateOf(img).y).toBeCloseTo(-12.5, 5)
  })

  it('pans by the pointer delta while dragging', () => {
    open()
    const viewport = screen.getByTestId('map-viewport')
    expect(translateOf(viewerImage())).toEqual({ x: 0, y: 0 })

    fireEvent.pointerDown(viewport, { pointerId: 1, clientX: 200, clientY: 200 })
    fireEvent.pointerMove(viewport, { pointerId: 1, clientX: 260, clientY: 170 })
    expect(translateOf(viewerImage())).toEqual({ x: 60, y: -30 })

    // A second move accumulates from the previous position, it does not restart from 0.
    fireEvent.pointerMove(viewport, { pointerId: 1, clientX: 280, clientY: 170 })
    expect(translateOf(viewerImage())).toEqual({ x: 80, y: -30 })

    fireEvent.pointerUp(viewport, { pointerId: 1 })
  })

  it('ignores pointer movement that never started with a pointerdown', () => {
    open()
    const viewport = screen.getByTestId('map-viewport')
    fireEvent.pointerMove(viewport, { pointerId: 7, clientX: 500, clientY: 500 })
    expect(translateOf(viewerImage())).toEqual({ x: 0, y: 0 })
  })

  it('pinch-zooms on two pointers by the change in their separation', () => {
    open()
    const viewport = screen.getByTestId('map-viewport')
    fireEvent.pointerDown(viewport, { pointerId: 1, clientX: -50, clientY: 0 })
    fireEvent.pointerDown(viewport, { pointerId: 2, clientX: 50, clientY: 0 })
    // First two-pointer move only establishes the baseline separation (100px).
    fireEvent.pointerMove(viewport, { pointerId: 2, clientX: 50, clientY: 0 })
    expect(scaleOf(viewerImage())).toBeCloseTo(1, 5)

    // Spreading to 200px doubles the scale.
    fireEvent.pointerMove(viewport, { pointerId: 2, clientX: 150, clientY: 0 })
    expect(scaleOf(viewerImage())).toBeCloseTo(2, 5)
  })

  it('double-click toggles between fit and 1:1', () => {
    open()
    const viewport = screen.getByTestId('map-viewport')
    // Opens at 1:1 in jsdom (no measurable viewport), so the first double-click fits...
    expect(scaleOf(viewerImage())).toBeCloseTo(1, 5)
    fireEvent.doubleClick(viewport)
    expect(scaleOf(viewerImage())).toBeCloseTo(1, 5)

    // ...and from any other zoom level it returns to 1:1.
    fireEvent.click(screen.getByRole('button', { name: 'Zoom in' }))
    expect(scaleOf(viewerImage())).toBeCloseTo(1.25, 5)
    fireEvent.doubleClick(viewport)
    expect(scaleOf(viewerImage())).toBeCloseTo(1, 5)
  })

  it('resets pan as well as zoom when fitting', () => {
    open()
    const viewport = screen.getByTestId('map-viewport')
    fireEvent.pointerDown(viewport, { pointerId: 1, clientX: 0, clientY: 0 })
    fireEvent.pointerMove(viewport, { pointerId: 1, clientX: 90, clientY: 90 })
    expect(translateOf(viewerImage())).toEqual({ x: 90, y: 90 })

    fireEvent.click(screen.getByRole('button', { name: 'Fit map to screen' }))
    expect(translateOf(viewerImage())).toEqual({ x: 0, y: 0 })
  })

  it('offers the raw PNG in a new tab', () => {
    open()
    const link = screen.getByRole('link', { name: 'Open PNG' })
    expect(link).toHaveAttribute('href', SRC)
    expect(link).toHaveAttribute('target', '_blank')
  })

  it('supports +/-/0/1 keyboard shortcuts', () => {
    open()
    fireEvent.keyDown(window, { key: '+' })
    expect(scaleOf(viewerImage())).toBeCloseTo(1.25, 5)
    fireEvent.keyDown(window, { key: '-' })
    expect(scaleOf(viewerImage())).toBeCloseTo(1, 5)
    fireEvent.keyDown(window, { key: '+' })
    fireEvent.keyDown(window, { key: '1' })
    expect(scaleOf(viewerImage())).toBeCloseTo(1, 5)
  })

  it('locks background scrolling only while open', () => {
    render(<MapViewer src={SRC} alt="Board — S1901M" />)
    expect(document.body.style.overflow).not.toBe('hidden')

    fireEvent.click(screen.getByRole('button', { name: /enlarge map/i }))
    expect(document.body.style.overflow).toBe('hidden')

    fireEvent.click(screen.getByRole('button', { name: 'Close map viewer' }))
    expect(document.body.style.overflow).not.toBe('hidden')
  })

  it('scales to fit once the image reports a natural size larger than the viewport', () => {
    open()
    const img = viewerImage()
    // jsdom never fires load; simulate a 1835x1360 render arriving. clientWidth is 0
    // here, so the documented 1:1 fallback applies rather than a divide-by-zero.
    Object.defineProperty(img, 'naturalWidth', { value: 1835, configurable: true })
    Object.defineProperty(img, 'naturalHeight', { value: 1360, configurable: true })
    fireEvent.load(img)
    expect(scaleOf(viewerImage())).toBeCloseTo(1, 5)
  })

  it('removes its key handler on unmount so Escape stops being intercepted', () => {
    const removeSpy = vi.spyOn(window, 'removeEventListener')
    open()
    fireEvent.click(screen.getByRole('button', { name: 'Close map viewer' }))
    expect(removeSpy).toHaveBeenCalledWith('keydown', expect.any(Function), true)
    removeSpy.mockRestore()
  })
})
