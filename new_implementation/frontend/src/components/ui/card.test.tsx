import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  CardDescription,
} from './card'

describe('Card', () => {
  it('renders Card with children', () => {
    render(<Card data-testid="card">Content</Card>)
    expect(screen.getByTestId('card')).toHaveTextContent('Content')
  })

  it('renders CardHeader and CardTitle', () => {
    render(
      <Card>
        <CardHeader>
          <CardTitle>Title</CardTitle>
        </CardHeader>
      </Card>
    )
    expect(screen.getByText('Title')).toBeInTheDocument()
  })

  it('renders CardContent', () => {
    render(
      <Card>
        <CardContent>Body</CardContent>
      </Card>
    )
    expect(screen.getByText('Body')).toBeInTheDocument()
  })

  it('renders CardDescription', () => {
    render(
      <Card>
        <CardHeader>
          <CardTitle>Title</CardTitle>
          <CardDescription>Description text</CardDescription>
        </CardHeader>
      </Card>
    )
    expect(screen.getByText('Description text')).toBeInTheDocument()
  })
})
