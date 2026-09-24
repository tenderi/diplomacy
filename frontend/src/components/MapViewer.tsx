/**
 * Inline board map plus a full-viewport zoom/pan viewer.
 *
 * Why this exists (Track I1): the renderer emits 1835x1360 PNGs and `AppLayout` is a
 * `max-w-4xl` (896px) column, so an inline `max-w-full` image is downscaled to ~47% --
 * below the size at which a 32px unit icon or an order arrow is readable. The inline map
 * is therefore a button that opens this viewer, where the same PNG can be inspected at
 * 1:1 and panned.
 *
 * Zoom/pan is hand-rolled rather than pulled from a library: the whole interaction is a
 * single CSS transform, and the repo has no pan/zoom dependency to reuse.
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { cn } from '@/lib/utils'

/** Zoom bounds. 1 = the image's natural pixel size (1:1). */
const MIN_SCALE = 0.1
const MAX_SCALE = 6
/** Multiplier per zoom-button press / wheel notch. */
const ZOOM_STEP = 1.25

type Transform = { scale: number; x: number; y: number }

const IDENTITY: Transform = { scale: 1, x: 0, y: 0 }

function clampScale(scale: number): number {
  return Math.min(MAX_SCALE, Math.max(MIN_SCALE, scale))
}

/**
 * Scale about a fixed point so the pixel under the cursor stays under the cursor.
 * `px`/`py` are relative to the transform's origin (the centre of the viewport).
 */
function zoomAbout(t: Transform, factor: number, px: number, py: number): Transform {
  const scale = clampScale(t.scale * factor)
  // Guard the no-op case so hitting a bound doesn't drift the image.
  if (scale === t.scale) return t
  const ratio = scale / t.scale
  return {
    scale,
    x: px - (px - t.x) * ratio,
    y: py - (py - t.y) * ratio,
  }
}

export interface MapViewerProps {
  /** Map PNG URL. */
  src: string
  /** Describes the map for both the inline image and the dialog (e.g. "Board, S1901M"). */
  alt: string
  className?: string
}

export default function MapViewer({ src, alt, className }: MapViewerProps) {
  const [open, setOpen] = useState(false)

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label={`Enlarge map: ${alt}`}
        title="Click to enlarge"
        className={cn(
          'group relative block w-full cursor-zoom-in overflow-hidden rounded-md border border-border',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
          className,
        )}
      >
        <img src={src} alt={alt} data-testid="map-inline" className="block h-auto w-full" />
        <span
          aria-hidden="true"
          className={cn(
            'pointer-events-none absolute bottom-2 right-2 rounded bg-black/70 px-2 py-1',
            'text-xs font-medium text-white opacity-0 transition-opacity',
            'group-hover:opacity-100 group-focus-visible:opacity-100',
          )}
        >
          Click to enlarge
        </span>
      </button>
      {open && <MapLightbox src={src} alt={alt} onClose={() => setOpen(false)} />}
    </>
  )
}

interface MapLightboxProps {
  src: string
  alt: string
  onClose: () => void
}

function MapLightbox({ src, alt, onClose }: MapLightboxProps) {
  const [transform, setTransform] = useState<Transform>(IDENTITY)
  /** Natural image size, needed to compute the "fit to viewport" scale. */
  const [natural, setNatural] = useState<{ w: number; h: number } | null>(null)
  const [fitted, setFitted] = useState(false)
  const dialogRef = useRef<HTMLDivElement>(null)
  const viewportRef = useRef<HTMLDivElement>(null)
  /** Active pointers, for drag-to-pan and two-finger pinch. */
  const pointers = useRef(new Map<number, { x: number; y: number }>())
  /** Pinch baseline: distance between the two pointers on the previous move. */
  const pinchDist = useRef<number | null>(null)
  const [dragging, setDragging] = useState(false)

  const fitScale = useCallback((): number => {
    const vp = viewportRef.current
    if (!natural || !vp) return 1
    const w = vp.clientWidth
    const h = vp.clientHeight
    // clientWidth/Height are 0 in jsdom; fall back to 1:1 rather than dividing to 0.
    if (!w || !h) return 1
    return clampScale(Math.min(w / natural.w, h / natural.h))
  }, [natural])

  const fitToViewport = useCallback(() => {
    setTransform({ scale: fitScale(), x: 0, y: 0 })
  }, [fitScale])

  // Open fitted to the viewport, so the first thing seen is the whole board -- the
  // inline map's failing is scale, not framing. 1:1 is a double-click away.
  useEffect(() => {
    if (natural && !fitted) {
      setFitted(true)
      fitToViewport()
    }
  }, [natural, fitted, fitToViewport])

  useEffect(() => {
    dialogRef.current?.focus()
  }, [])

  // Suppress background scroll while the overlay owns the viewport.
  useEffect(() => {
    const previous = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = previous
    }
  }, [])

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.stopPropagation()
        onClose()
      } else if (e.key === '+' || e.key === '=') {
        setTransform((t) => zoomAbout(t, ZOOM_STEP, 0, 0))
      } else if (e.key === '-' || e.key === '_') {
        setTransform((t) => zoomAbout(t, 1 / ZOOM_STEP, 0, 0))
      } else if (e.key === '0') {
        fitToViewport()
      } else if (e.key === '1') {
        setTransform({ scale: 1, x: 0, y: 0 })
      }
    }
    // Capture phase: the map lives inside a page with its own key handling, and Esc
    // here must not also reach whatever is behind the overlay.
    window.addEventListener('keydown', onKeyDown, true)
    return () => window.removeEventListener('keydown', onKeyDown, true)
  }, [onClose, fitToViewport])

  /** Cursor position relative to the viewport centre, which is the transform origin. */
  const toOrigin = (clientX: number, clientY: number): { px: number; py: number } => {
    const vp = viewportRef.current
    if (!vp) return { px: 0, py: 0 }
    const r = vp.getBoundingClientRect()
    return { px: clientX - (r.left + r.width / 2), py: clientY - (r.top + r.height / 2) }
  }

  const onWheel = (e: React.WheelEvent) => {
    e.preventDefault()
    const { px, py } = toOrigin(e.clientX, e.clientY)
    const factor = e.deltaY < 0 ? ZOOM_STEP : 1 / ZOOM_STEP
    setTransform((t) => zoomAbout(t, factor, px, py))
  }

  const onPointerDown = (e: React.PointerEvent) => {
    pointers.current.set(e.pointerId, { x: e.clientX, y: e.clientY })
    e.currentTarget.setPointerCapture?.(e.pointerId)
    if (pointers.current.size === 1) setDragging(true)
  }

  const onPointerMove = (e: React.PointerEvent) => {
    const previous = pointers.current.get(e.pointerId)
    if (!previous) return
    pointers.current.set(e.pointerId, { x: e.clientX, y: e.clientY })

    if (pointers.current.size >= 2) {
      // Pinch: zoom about the midpoint by the change in pointer separation.
      const [a, b] = Array.from(pointers.current.values())
      const dist = Math.hypot(a.x - b.x, a.y - b.y)
      if (pinchDist.current !== null && pinchDist.current > 0) {
        const { px, py } = toOrigin((a.x + b.x) / 2, (a.y + b.y) / 2)
        const factor = dist / pinchDist.current
        setTransform((t) => zoomAbout(t, factor, px, py))
      }
      pinchDist.current = dist
      return
    }

    const dx = e.clientX - previous.x
    const dy = e.clientY - previous.y
    setTransform((t) => ({ ...t, x: t.x + dx, y: t.y + dy }))
  }

  const endPointer = (e: React.PointerEvent) => {
    pointers.current.delete(e.pointerId)
    if (pointers.current.size < 2) pinchDist.current = null
    if (pointers.current.size === 0) setDragging(false)
  }

  const atNaturalSize = Math.abs(transform.scale - 1) < 0.01
  const zoomPercent = Math.round(transform.scale * 100)

  return (
    <div
      ref={dialogRef}
      role="dialog"
      aria-modal="true"
      aria-label={`Map viewer: ${alt}`}
      tabIndex={-1}
      className="fixed inset-0 z-50 flex flex-col bg-black/90 outline-none"
    >
      <div className="flex flex-wrap items-center gap-2 border-b border-white/15 px-3 py-2 text-white">
        <span className="mr-auto truncate text-sm font-medium">{alt}</span>
        <ViewerButton onClick={() => setTransform((t) => zoomAbout(t, 1 / ZOOM_STEP, 0, 0))} label="Zoom out">
          &minus;
        </ViewerButton>
        <span className="w-14 text-center text-xs tabular-nums" aria-live="polite">
          {zoomPercent}%
        </span>
        <ViewerButton onClick={() => setTransform((t) => zoomAbout(t, ZOOM_STEP, 0, 0))} label="Zoom in">
          +
        </ViewerButton>
        <ViewerButton onClick={fitToViewport} label="Fit map to screen">
          Fit
        </ViewerButton>
        <ViewerButton onClick={() => setTransform({ scale: 1, x: 0, y: 0 })} label="Show map at full size">
          1:1
        </ViewerButton>
        <a
          href={src}
          target="_blank"
          rel="noreferrer"
          className="rounded border border-white/25 px-2 py-1 text-xs hover:bg-white/15"
        >
          Open PNG
        </a>
        <ViewerButton onClick={onClose} label="Close map viewer">
          &times;
        </ViewerButton>
      </div>

      <div
        ref={viewportRef}
        data-testid="map-viewport"
        onWheel={onWheel}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={endPointer}
        onPointerCancel={endPointer}
        onDoubleClick={() => (atNaturalSize ? fitToViewport() : setTransform({ scale: 1, x: 0, y: 0 }))}
        className={cn(
          'relative flex-1 touch-none overflow-hidden',
          dragging ? 'cursor-grabbing' : 'cursor-grab',
        )}
      >
        <img
          src={src}
          alt={alt}
          draggable={false}
          onLoad={(e) => {
            const img = e.currentTarget
            setNatural({ w: img.naturalWidth || 1, h: img.naturalHeight || 1 })
          }}
          style={{
            transform: `translate(-50%, -50%) translate(${transform.x}px, ${transform.y}px) scale(${transform.scale})`,
          }}
          className="absolute left-1/2 top-1/2 max-w-none origin-center select-none"
        />
      </div>

      <p className="border-t border-white/15 px-3 py-1.5 text-center text-xs text-white/60">
        Drag to pan &middot; scroll or pinch to zoom &middot; double-click toggles 1:1 &middot; Esc closes
      </p>
    </div>
  )
}

function ViewerButton({
  onClick,
  label,
  children,
}: {
  onClick: () => void
  label: string
  children: React.ReactNode
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      title={label}
      className="min-w-8 rounded border border-white/25 px-2 py-1 text-xs leading-none hover:bg-white/15"
    >
      {children}
    </button>
  )
}
