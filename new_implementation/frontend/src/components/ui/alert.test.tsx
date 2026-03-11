import { describe, it, expect } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import { Alert, AlertDescription, AlertTitle } from './alert'

describe('Alert', () => {
  it('renders with role alert', () => {
    const { container } = render(<Alert>Message</Alert>)
    expect(within(container).getByRole('alert')).toHaveTextContent('Message')
  })

  it('renders default variant', () => {
    const { container } = render(<Alert data-testid="alert">Content</Alert>)
    expect(within(container).getByTestId('alert')).toBeInTheDocument()
  })

  it('renders destructive variant', () => {
    const { container } = render(<Alert variant="destructive">Error</Alert>)
    expect(within(container).getByRole('alert')).toHaveTextContent('Error')
  })

  it('renders AlertTitle and AlertDescription', () => {
    const { container } = render(
      <Alert>
        <AlertTitle>Title</AlertTitle>
        <AlertDescription>Description</AlertDescription>
      </Alert>
    )
    expect(within(container).getByText('Title')).toBeInTheDocument()
    expect(within(container).getByText('Description')).toBeInTheDocument()
  })
})
