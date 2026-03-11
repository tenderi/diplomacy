import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, within } from '@testing-library/react'
import { Textarea } from './textarea'

describe('Textarea', () => {
  it('renders with value', () => {
    const { container } = render(<Textarea value="hello" onChange={() => {}} data-testid="textarea" />)
    expect(within(container).getByTestId('textarea')).toHaveValue('hello')
  })

  it('calls onChange when typing', () => {
    const handleChange = vi.fn()
    const { container } = render(<Textarea value="" onChange={handleChange} data-testid="textarea" />)
    fireEvent.change(within(container).getByTestId('textarea'), { target: { value: 'x' } })
    expect(handleChange).toHaveBeenCalled()
  })

  it('can be disabled', () => {
    const { container } = render(<Textarea disabled data-testid="textarea" />)
    expect(within(container).getByTestId('textarea')).toBeDisabled()
  })
})
