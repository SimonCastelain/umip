'use client'

import './globals.css'
import '@rainbow-me/rainbowkit/styles.css'

import { RainbowKitProvider, darkTheme } from '@rainbow-me/rainbowkit'
import { WagmiProvider }                  from 'wagmi'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useState }                        from 'react'
import { config }                          from '@/lib/wagmi'

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(() => new QueryClient())

  return (
    <html lang="en">
      <head>
        <title>UMIP Sandbox — Test Unified Collateral on Sepolia</title>
        <meta name="description" content="Interactive testnet demo of UMIP — unified collateral management across perpetual DEXes" />
      </head>
      <body className="bg-gray-950 text-gray-100 min-h-screen">
        <WagmiProvider config={config}>
          <QueryClientProvider client={queryClient}>
            <RainbowKitProvider theme={darkTheme()}>
              {children}
            </RainbowKitProvider>
          </QueryClientProvider>
        </WagmiProvider>
      </body>
    </html>
  )
}
