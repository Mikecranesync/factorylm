export default function Hub() {
  return (
    <div className="h-full flex flex-col">
      <div className="mb-4">
        <h2 className="text-xl font-bold">Ladder Logic Editor</h2>
        <p className="text-sm text-gray-400">Micro 820 — live reference view</p>
      </div>
      <div className="flex-1 rounded-lg overflow-hidden border border-gray-800">
        <iframe
          src="https://mikecranesync.github.io/ladder-logic-editor/"
          className="w-full h-full"
          style={{ border: "none" }}
          title="Ladder Logic Editor"
        />
      </div>
    </div>
  )
}
