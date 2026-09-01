export function Loading({ what = 'data' }: { what?: string }) {
  return <p className="py-12 text-center text-sm text-neutral-500">Loading {what}…</p>
}

export function ErrorNote({ error }: { error: Error }) {
  return (
    <div className="rounded-lg border border-red-900/60 bg-red-950/30 p-4 text-sm">
      <p className="font-medium text-red-300">Could not load data</p>
      <p className="mt-1 text-red-400/80">{error.message}</p>
      <p className="mt-2 text-neutral-500">
        If this is a fresh checkout, run <code className="text-neutral-300">milb ingest</code> then{' '}
        <code className="text-neutral-300">milb export</code> to generate the JSON.
      </p>
    </div>
  )
}
