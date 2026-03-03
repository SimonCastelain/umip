'use client'

import { getDefaultConfig } from '@rainbow-me/rainbowkit'
import { arbitrumSepolia } from 'wagmi/chains'

export const config = getDefaultConfig({
  appName: 'UMIP Sandbox',
  projectId: process.env.NEXT_PUBLIC_WALLETCONNECT_PROJECT_ID ?? 'umip-sandbox-demo',
  chains: [arbitrumSepolia],
  ssr: true,
})
