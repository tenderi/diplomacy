import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, within } from '@testing-library/react'
import { Input } from './input'

describe('Input', () => {
  it('renders with value and type', () => {
    const { container } = render(<Input value="test" onChange={() => {}} type="email" data-testid="input" />)
    const input = within(container).getByTestId('input')
    expect(input).toHaveValue('test')
    expect(input).toHaveAttribute('type', 'email')
  })

  it('calls onChange when typing', () => {
    const handleChange = vi.fn()
    const { container } = render(<Input value="" onChange={handleChange} data-testid="input" />)
    fireEvent.change(within(container).getByTestId('input'), { target: { value: 'x' } })
    expect(handleChange).toHaveBeenCalled()
  })

  it('can be disabled', () => {
    const { container } = render(<Input disabled data-testid="input" />)
    expect(within(container).getByTestId('input')).toBeDisabled()
  })

  it('associates with label via id', () => {
    const { container } = render(
      <>
        <label htmlFor="email">Email</label>
        <Input id="email" data-testid="input" />
      </>
    )
    const input = within(container).getByTestId('input')
    expect(input).toHaveAttribute('id', 'email')
    expect(within(container).getByLabelText('Email')).toBe(input)
  })
})
