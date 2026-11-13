import { createRef } from 'react'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { Button } from './button'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from './alert-dialog'

afterEach(cleanup)

describe('Button', () => {
  it('forwards a ref to the DOM button', () => {
    const ref = createRef<HTMLButtonElement>()
    render(<Button ref={ref}>Go</Button>)
    expect(ref.current).toBe(screen.getByRole('button', { name: 'Go' }))
  })

  it('gives no ref warning inside an AlertDialogTrigger asChild', () => {
    const err = vi.spyOn(console, 'error').mockImplementation(() => {})
    render(
      <AlertDialog>
        <AlertDialogTrigger asChild>
          <Button>Open</Button>
        </AlertDialogTrigger>
      </AlertDialog>,
    )
    expect(err.mock.calls.map((c) => String(c[0]))).toEqual([])
    err.mockRestore()
  })

  it('logs no console error when a confirm dialog is opened', () => {
    const err = vi.spyOn(console, 'error').mockImplementation(() => {})
    render(
      <AlertDialog>
        <AlertDialogTrigger asChild>
          <Button>Open</Button>
        </AlertDialogTrigger>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Sure?</AlertDialogTitle>
            <AlertDialogDescription>This cannot be undone.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction>Confirm</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>,
    )
    fireEvent.click(screen.getByRole('button', { name: 'Open' }))
    expect(screen.getByRole('button', { name: 'Confirm' }).dataset.slot).toBe('alert-dialog-action')
    expect(err.mock.calls.map((c) => String(c[0]))).toEqual([])
    err.mockRestore()
  })

  it('is at least 40 px tall below sm and compact from sm up', () => {
    render(<Button size="sm">Tap</Button>)
    const cls = screen.getByRole('button', { name: 'Tap' }).className
    expect(cls).toContain('h-10')
    expect(cls).toContain('sm:h-7')
  })
})
