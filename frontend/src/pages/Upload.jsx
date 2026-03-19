import { useState } from 'react';
import { motion } from 'framer-motion';
import { Upload as UploadIcon, File, CheckCircle, AlertCircle, Trash2, Lock, Menu } from 'lucide-react';
import toast from 'react-hot-toast';
import { uploadAPI } from '../lib/api';
import Sidebar from '../components/Sidebar';

const ACCESS_LEVELS = [
  { value: 'level_1', label: 'General',    sub: 'All authenticated users',  color: 'text-success', border: 'border-success/30', bg: 'bg-success/10' },
  { value: 'level_2', label: 'Legal Team', sub: 'Admin and owner only',      color: 'text-warning', border: 'border-warning/30', bg: 'bg-warning/10' },
  { value: 'level_3', label: 'Privileged', sub: 'Owner only',                color: 'text-danger',  border: 'border-danger/30',  bg: 'bg-danger/10'  },
];

export default function Upload() {
  const [files,          setFiles]          = useState([]);
  const [uploading,      setUploading]      = useState(false);
  const [uploadProgress, setUploadProgress] = useState({});
  const [accessLevel,    setAccessLevel]    = useState('level_1');
  const [sidebarOpen,    setSidebarOpen]    = useState(false);

  const addFiles = (incoming) => {
    const pdfs = Array.from(incoming).filter(f => f.type === 'application/pdf');
    if (!pdfs.length) { toast.error('Only PDF files are supported'); return; }
    setFiles(p => [...p, ...pdfs]);
    toast.success(`Added ${pdfs.length} file${pdfs.length > 1 ? 's' : ''}`);
  };

  const handleDrop = (e) => { e.preventDefault(); addFiles(e.dataTransfer.files); };
  const handleFileInput = (e) => addFiles(e.target.files || []);
  const removeFile = (i) => setFiles(p => p.filter((_, idx) => idx !== i));

  const handleUpload = async () => {
    if (!files.length) { toast.error('Select at least one file'); return; }
    setUploading(true);
    let ok = 0, fail = 0;

    for (let i = 0; i < files.length; i++) {
      setUploadProgress(p => ({ ...p, [i]: 'uploading' }));
      try {
        await uploadAPI.upload(files[i], accessLevel);
        setUploadProgress(p => ({ ...p, [i]: 'success' }));
        ok++;
        toast.success(`${files[i].name} uploaded`, { duration: 2000 });
      } catch (err) {
        let msg = 'Upload failed';
        if (err.response?.status === 429) msg = 'Rate limited — please wait';
        else if (err.response?.status === 401) msg = 'Session expired';
        else if (err.response?.status === 403) msg = 'Insufficient permissions';
        else if (err.response?.data?.detail)   msg = err.response.data.detail;
        setUploadProgress(p => ({ ...p, [i]: 'error' }));
        fail++;
        toast.error(`${files[i].name}: ${msg}`, { duration: 4000 });
      }
    }

    setUploading(false);
    if (ok > 0 && fail === 0) {
      toast.success(`All ${ok} file${ok > 1 ? 's' : ''} uploaded`);
      setFiles([]); setUploadProgress({});
    } else if (ok > 0) {
      toast(`${ok} uploaded, ${fail} failed`, { icon: '⚠️' });
    }
  };

  const selected = ACCESS_LEVELS.find(l => l.value === accessLevel);

  return (
    <div className="flex h-[100dvh] bg-base">
      <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      <div className="flex-1 flex flex-col overflow-hidden">

        {/* Header */}
        <div className="border-b border-stroke bg-surface flex-shrink-0">
          <div className="max-w-3xl mx-auto px-4 md:px-6 py-3 flex items-center gap-3">
            <button
              onClick={() => setSidebarOpen(true)}
              className="md:hidden p-1.5 text-ink-faint hover:text-ink hover:bg-elevated rounded-sm transition-colors"
            >
              <Menu className="w-4 h-4" />
            </button>
            <UploadIcon className="w-4 h-4 text-gold" />
            <div>
              <h1 className="text-sm font-medium text-ink tracking-wide">Upload Documents</h1>
              <p className="text-xs text-ink-faint hidden md:block">PDF files only · Max 50 MB</p>
            </div>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto">
          <div className="max-w-3xl mx-auto px-4 md:px-6 py-6 space-y-4">

            {/* Access level */}
            <div className="bg-surface border border-stroke rounded-sm">
              <div className="px-4 py-3 border-b border-stroke flex items-center gap-2">
                <Lock className="w-3.5 h-3.5 text-ink-faint" />
                <span className="text-xs font-mono text-ink-muted uppercase tracking-widest">Clearance Level</span>
              </div>
              <div className="p-4 grid grid-cols-1 sm:grid-cols-3 gap-2">
                {ACCESS_LEVELS.map(l => (
                  <button
                    key={l.value}
                    type="button"
                    onClick={() => setAccessLevel(l.value)}
                    disabled={uploading}
                    className={`
                      text-left p-3 rounded-sm border transition-all duration-150 disabled:opacity-50
                      ${accessLevel === l.value
                        ? `${l.bg} ${l.border}`
                        : 'bg-elevated border-stroke hover:border-stroke-strong'
                      }
                    `}
                  >
                    <p className={`text-xs font-mono font-medium ${accessLevel === l.value ? l.color : 'text-ink'}`}>
                      {l.label}
                    </p>
                    <p className="text-xs text-ink-faint mt-0.5">{l.sub}</p>
                  </button>
                ))}
              </div>
              {accessLevel !== 'level_1' && (
                <div className="px-4 pb-3">
                  <p className="text-xs text-warning font-mono">
                    ⚠ Restricted — only users with sufficient clearance will see this in results.
                  </p>
                </div>
              )}
            </div>

            {/* Drop zone */}
            <div
              onDragOver={e => e.preventDefault()}
              onDrop={handleDrop}
              className="bg-surface border-2 border-dashed border-stroke hover:border-gold/40 rounded-sm p-12 text-center transition-colors cursor-pointer"
              onClick={() => !uploading && document.getElementById('file-input').click()}
            >
              <input
                id="file-input" type="file" multiple accept=".pdf"
                onChange={handleFileInput} disabled={uploading} className="hidden"
              />
              <UploadIcon className="w-8 h-8 text-ink-faint mx-auto mb-3" />
              <p className="text-sm text-ink mb-1">Drag and drop PDFs here</p>
              <p className="text-xs text-ink-faint mb-4">or click to browse</p>
              <span className="px-4 py-2 bg-elevated border border-stroke rounded-sm text-xs font-mono text-ink-muted hover:border-stroke-strong transition-colors">
                Browse Files
              </span>
            </div>

            {/* File list */}
            {files.length > 0 && (
              <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
                <div className="bg-surface border border-stroke rounded-sm overflow-hidden">
                  <div className="px-4 py-3 border-b border-stroke flex items-center justify-between">
                    <span className="text-xs font-mono text-ink-muted uppercase tracking-widest">
                      {files.length} file{files.length > 1 ? 's' : ''} selected
                    </span>
                    <span className={`text-xs font-mono px-2 py-0.5 rounded-sm border ${selected.bg} ${selected.border} ${selected.color}`}>
                      {selected.label}
                    </span>
                  </div>

                  {files.map((file, idx) => (
                    <div
                      key={idx}
                      className={`flex items-center justify-between px-4 py-3 ${idx < files.length - 1 ? 'border-b border-stroke' : ''}`}
                    >
                      <div className="flex items-center gap-3 flex-1 min-w-0">
                        <File className="w-3.5 h-3.5 text-gold flex-shrink-0" />
                        <div className="min-w-0">
                          <p className="text-sm text-ink truncate">{file.name}</p>
                          <p className="text-xs text-ink-faint font-mono">{(file.size / 1024 / 1024).toFixed(2)} MB</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-2 ml-3 flex-shrink-0">
                        {uploadProgress[idx] === 'success' && (
                          <span className="flex items-center gap-1 text-xs text-success font-mono">
                            <CheckCircle className="w-3.5 h-3.5" /> Done
                          </span>
                        )}
                        {uploadProgress[idx] === 'error' && (
                          <span className="flex items-center gap-1 text-xs text-danger font-mono">
                            <AlertCircle className="w-3.5 h-3.5" /> Failed
                          </span>
                        )}
                        {uploadProgress[idx] === 'uploading' && (
                          <div className="w-20 h-1 bg-elevated rounded-full overflow-hidden">
                            <div className="h-full bg-gold animate-pulse w-2/3" />
                          </div>
                        )}
                        {!uploadProgress[idx] && (
                          <button
                            onClick={() => removeFile(idx)}
                            disabled={uploading}
                            className="p-1 text-ink-faint hover:text-danger disabled:opacity-40 transition-colors"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>

                <button
                  onClick={handleUpload}
                  disabled={uploading}
                  className="w-full mt-3 py-2.5 bg-gold text-ink-inverse text-xs font-mono font-medium tracking-widest uppercase rounded-sm hover:bg-gold/90 active:bg-gold/80 transition-all disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                >
                  {uploading
                    ? `Uploading ${files.length} file${files.length > 1 ? 's' : ''}…`
                    : `Upload ${files.length} file${files.length > 1 ? 's' : ''} as ${selected.label}`
                  }
                </button>
              </motion.div>
            )}

          </div>
        </div>
      </div>
    </div>
  );
}