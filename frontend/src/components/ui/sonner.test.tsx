import { describe, expect, it } from 'vitest'
import { act, render, waitFor } from '@testing-library/react'
import { toast } from 'sonner'
import { Toaster } from './sonner'

describe('Toaster', () => {
  it('drops the 100% width on phones so the toast stays inside the viewport', async () => {
    render(<Toaster position="top-center" />)
    act(() => {
      toast.success('hello')
    })
    await waitFor(() => expect(document.querySelector('[data-sonner-toaster]')).not.toBeNull())
    expect(document.querySelector('[data-sonner-toaster]')?.className).toContain('max-sm:!w-auto')
  })
})
