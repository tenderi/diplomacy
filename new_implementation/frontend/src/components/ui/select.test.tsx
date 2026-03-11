import { describe, it, expect } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from './select'

describe('Select', () => {
  it('renders trigger and value placeholder', () => {
    const { container } = render(
      <Select>
        <SelectTrigger data-testid="trigger">
          <SelectValue placeholder="Choose" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="a">Option A</SelectItem>
          <SelectItem value="b">Option B</SelectItem>
        </SelectContent>
      </Select>
    )
    expect(within(container).getByTestId('trigger')).toBeInTheDocument()
    expect(within(container).getByText('Choose')).toBeInTheDocument()
  })

  it('renders combobox trigger', () => {
    const { container } = render(
      <Select>
        <SelectTrigger>
          <SelectValue placeholder="Choose" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="a">Option A</SelectItem>
        </SelectContent>
      </Select>
    )
    expect(within(container).getByRole('combobox')).toBeInTheDocument()
  })
})
