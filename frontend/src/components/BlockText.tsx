// A parsed block's text: a real table for table blocks, otherwise the text with its line breaks.
export function BlockText({ text, table }: { text: string; table?: string[][] }) {
  if (table?.length) {
    const [head, ...rows] = table
    const columns = Math.max(...table.map((r) => r.length))
    const pad = (row: string[]) => [...row, ...Array<string>(columns - row.length).fill('')]
    return (
      <div className="overflow-x-auto rounded-control border border-border">
        <table className="w-full border-collapse text-small text-text">
          <thead className="bg-surface-muted">
            <tr>
              {pad(head).map((cell, i) => (
                <th key={i} className="border-b border-border px-3 py-2 text-left align-top font-medium">
                  {cell}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, r) => (
              <tr key={r} className="border-b border-border last:border-b-0">
                {pad(row).map((cell, i) => (
                  <td key={i} className="px-3 py-2 align-top">
                    {cell}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )
  }
  return <p className="text-small whitespace-pre-line text-text">{text}</p>
}
