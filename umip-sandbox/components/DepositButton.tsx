'use client'

import { useState }                                        from 'react'
import { useWriteContract, useReadContract, useAccount }   from 'wagmi'
import { parseUnits, maxUint256 }                          from 'viem'
import { VAULT_ADDRESS, USDC_ADDRESS, VAULT_ABI, ERC20_ABI } from '@/lib/contracts'

type Mode = 'deposit' | 'withdraw'

export function DepositButton({ onSuccess }: { onSuccess?: () => void }) {
  const { address } = useAccount()
  const [amount, setAmount]     = useState('')
  const [mode, setMode]         = useState<Mode>('deposit')
  const [status, setStatus]     = useState<string | null>(null)
  const [isLoading, setLoading] = useState(false)

  const { data: allowance, refetch: refetchAllowance } = useReadContract({
    address: USDC_ADDRESS,
    abi:     ERC20_ABI,
    functionName: 'allowance',
    args:    address ? [address, VAULT_ADDRESS] : undefined,
    query:   { enabled: !!address },
  })

  const { writeContractAsync } = useWriteContract()

  async function handleDeposit() {
    if (!address || !amount) return
    setLoading(true)
    setStatus(null)
    try {
      const raw = parseUnits(amount, 6)

      // Step 1: Approve if needed
      if ((allowance ?? 0n) < raw) {
        setStatus('Approving USDC...')
        await writeContractAsync({
          address:      USDC_ADDRESS,
          abi:          ERC20_ABI,
          functionName: 'approve',
          args:         [VAULT_ADDRESS, maxUint256],
        })
        await refetchAllowance()
      }

      // Step 2: Deposit
      setStatus('Depositing into vault...')
      await writeContractAsync({
        address:      VAULT_ADDRESS,
        abi:          VAULT_ABI,
        functionName: 'deposit',
        args:         [raw],
      })

      setStatus(`✓ Deposited $${amount} USDC into vault`)
      setAmount('')
      onSuccess?.()
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e)
      setStatus(`Error: ${msg.slice(0, 100)}`)
    } finally {
      setLoading(false)
    }
  }

  async function handleWithdraw() {
    if (!address || !amount) return
    setLoading(true)
    setStatus(null)
    try {
      const raw = parseUnits(amount, 6)
      setStatus('Withdrawing from vault...')
      await writeContractAsync({
        address:      VAULT_ADDRESS,
        abi:          VAULT_ABI,
        functionName: 'withdraw',
        args:         [raw],
      })
      setStatus(`✓ Withdrew $${amount} USDC from vault`)
      setAmount('')
      onSuccess?.()
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e)
      setStatus(`Error: ${msg.slice(0, 100)}`)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6 space-y-4">
      <h2 className="text-lg font-semibold">Manage Collateral</h2>

      {/* Mode toggle */}
      <div className="flex gap-1 bg-gray-800 p-1 rounded-lg w-fit">
        {(['deposit', 'withdraw'] as const).map((m) => (
          <button
            key={m}
            onClick={() => setMode(m)}
            className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
              mode === m ? 'bg-gray-700 text-white' : 'text-gray-400 hover:text-white'
            }`}
          >
            {m.charAt(0).toUpperCase() + m.slice(1)}
          </button>
        ))}
      </div>

      {/* Amount input */}
      <div className="relative">
        <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400">$</span>
        <input
          type="number"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          placeholder="0.00"
          className="w-full bg-gray-800 border border-gray-700 rounded-xl pl-8 pr-16 py-3 text-white focus:outline-none focus:border-emerald-500 transition-colors"
        />
        <span className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 text-sm">USDC</span>
      </div>

      {/* Action button */}
      <button
        onClick={mode === 'deposit' ? handleDeposit : handleWithdraw}
        disabled={isLoading || !amount || !address}
        className={`w-full py-3 rounded-xl font-semibold transition-all ${
          mode === 'deposit'
            ? 'bg-emerald-600 hover:bg-emerald-500 disabled:bg-emerald-900 disabled:text-emerald-600'
            : 'bg-gray-700 hover:bg-gray-600 disabled:bg-gray-800 disabled:text-gray-600'
        } disabled:cursor-not-allowed`}
      >
        {isLoading ? 'Processing...' : mode === 'deposit' ? 'Deposit into Vault' : 'Withdraw from Vault'}
      </button>

      {/* Faucet link */}
      <a
        href="https://faucet.circle.com/"
        target="_blank"
        rel="noopener noreferrer"
        className="flex items-center justify-center gap-2 text-sm text-gray-400 hover:text-emerald-400 transition-colors"
      >
        <span>Need testnet USDC?</span>
        <span className="underline">Get it from Circle's faucet →</span>
      </a>

      {/* Status */}
      {status && (
        <p className={`text-sm rounded-lg px-4 py-3 ${
          status.startsWith('✓') ? 'bg-emerald-900/40 text-emerald-400' :
          status.startsWith('Error') ? 'bg-red-900/40 text-red-400' :
          'bg-gray-800 text-gray-300'
        }`}>
          {status}
        </p>
      )}
    </div>
  )
}
