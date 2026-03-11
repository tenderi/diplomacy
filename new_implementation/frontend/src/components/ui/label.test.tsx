import { describe, it, expect } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import { Label } from './label'

describe('Label', () => {
  it('renders children', () => {
    const { container } = render(<Label>Email</Label>)
    expect(within(container).getByText('Email')).toBeInTheDocument()
  })

  it('associates with input via htmlFor', () => {
    const { container } = render(
      <>
        <Label htmlFor="email">Email</Label>
        <input id="email" />
      </>
    )
    const label = within(container).getByText('Email')
    expect(label).toHaveAttribute('for', 'email')
  })
})
