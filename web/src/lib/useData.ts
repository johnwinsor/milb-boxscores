import { useEffect, useState } from 'react'
import { fetchMeta, fetchPlayer, fetchTeams, fetchWindow } from './api'
import type { Meta, PlayerDetail, TeamsDoc, WindowReport } from './types'

interface State<T> { data: T | null; error: Error | null; loading: boolean }

function useAsync<T>(fn: () => Promise<T>, deps: unknown[]): State<T> {
  const [state, setState] = useState<State<T>>({ data: null, error: null, loading: true })
  useEffect(() => {
    let cancelled = false
    setState((s) => ({ ...s, loading: true }))
    fn().then(
      (data) => !cancelled && setState({ data, error: null, loading: false }),
      (error) => !cancelled && setState({ data: null, error, loading: false }),
    )
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)
  return state
}

export const useMeta = () => useAsync<Meta>(fetchMeta, [])
export const useTeams = () => useAsync<TeamsDoc>(fetchTeams, [])
export const useWindow = (days: number) => useAsync<WindowReport>(() => fetchWindow(days), [days])
export const usePlayer = (id: number) => useAsync<PlayerDetail>(() => fetchPlayer(id), [id])
