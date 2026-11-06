import { useEffect, useState } from 'react'

const EMPTY = {
  preparedFor: '',
  matterName: '',
  matterReference: '',
  documentName: '',
  authorName: '',
  firmName: '',
}

export default function ExportModal({
  open,
  onClose,
  onConfirm,
  defaults = {},
  title = 'Export PDF — matter details',
}) {
  const [form, setForm] = useState({ ...EMPTY, ...defaults })

  useEffect(() => {
    if (open) setForm({ ...EMPTY, ...defaults })
  }, [open, defaults])

  if (!open) return null

  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }))

  const submit = (e) => {
    e.preventDefault()
    const required = [
      ['preparedFor', 'Prepared for (client)'],
      ['matterName', 'Matter / case name'],
      ['matterReference', 'Matter reference'],
      ['documentName', 'Document reviewed'],
      ['authorName', 'Author'],
      ['firmName', 'Firm / organization'],
    ]
    for (const [key, label] of required) {
      if (!form[key]?.trim()) {
        window.alert(`${label} is required for a professional export.`)
        return
      }
    }
    onConfirm(form)
  }

  return (
    <div className="modal-overlay" role="dialog" aria-modal="true">
      <form className="modal card contract-editor" style={{ maxWidth: 480 }} onSubmit={submit}>
        <h3>{title}</h3>
        <p className="muted">All fields are required for counsel-ready PDF exports.</p>
        <label>
          Prepared for (client)
          <input value={form.preparedFor} onChange={set('preparedFor')} placeholder="e.g. Acme GmbH" required />
        </label>
        <label>
          Matter / case name
          <input value={form.matterName} onChange={set('matterName')} placeholder="e.g. Acme — DPA review" required />
        </label>
        <label>
          Matter reference
          <input value={form.matterReference} onChange={set('matterReference')} placeholder="e.g. MAT-2026-0142" required />
        </label>
        <label>
          Document reviewed
          <input value={form.documentName} onChange={set('documentName')} placeholder="e.g. Mutual NDA v3.pdf" required />
        </label>
        <label>
          Author
          <input value={form.authorName} onChange={set('authorName')} placeholder="e.g. Jane Counsel" required />
        </label>
        <label>
          Firm / organization
          <input value={form.firmName} onChange={set('firmName')} placeholder="e.g. JurisGuard Legal" required />
        </label>
        <div className="row spread" style={{ marginTop: '1rem' }}>
          <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button type="submit" className="btn btn-primary">Generate PDF</button>
        </div>
      </form>
    </div>
  )
}
