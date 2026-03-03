import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'UMIP Live Dashboard — Agent V1 vs V2 Comparison',
  description: 'Real-time proof: UMIP eliminates capital fragmentation across perpetual DEXes. Agent V1 (fragmented) vs Agent V2 (unified vault) running on Arbitrum Sepolia.',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-gray-950 text-gray-100 min-h-screen">{children}</body>
    </html>
  )
}
