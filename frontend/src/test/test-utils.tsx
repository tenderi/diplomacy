import React, { ReactElement } from 'react'
import { render, RenderOptions } from '@testing-library/react'
import { MemoryRouter, MemoryRouterProps } from 'react-router-dom'
import { AuthProvider } from '@/contexts/AuthContext'

export interface RenderWithProvidersOptions extends Omit<RenderOptions, 'wrapper'> {
  routerProps?: Partial<MemoryRouterProps>
}

function AllProviders({
  children,
  routerProps = {},
}: {
  children: React.ReactNode
  routerProps?: Partial<MemoryRouterProps>
}) {
  return (
    <MemoryRouter {...routerProps}>
      <AuthProvider>{children}</AuthProvider>
    </MemoryRouter>
  )
}

export function renderWithProviders(
  ui: ReactElement,
  { routerProps = {}, ...renderOptions }: RenderWithProvidersOptions = {}
) {
  const defaultRouterProps: MemoryRouterProps = {
    initialEntries: ['/'],
    ...routerProps,
  }
  return render(ui, {
    wrapper: ({ children }) => (
      <AllProviders routerProps={defaultRouterProps}>{children}</AllProviders>
    ),
    ...renderOptions,
  })
}

export { screen, fireEvent, waitFor, within } from '@testing-library/react'
