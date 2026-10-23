import { createRef } from 'react'
import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { Button } from './button'
import { AlertDialog, AlertDialogTrigger } from './alert-dialog'

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

  it('is at least 40 px tall below sm and compact from sm up', () => {
    render(<Button size="sm">Tap</Button>)
    const cls = screen.getByRole('button', { name: 'Tap' }).className
    expect(cls).toContain('h-10')
    expect(cls).toContain('sm:h-7')
  })
})
