import { useState } from 'react';
import { motion } from 'framer-motion';
import { Upload as UploadIcon, File, CheckCircle, AlertCircle, Trash2, Lock } from 'lucide-react';
import toast from 'react-hot-toast';
import { uploadAPI } from '../lib/api';
import Button from '../components/ui/Button';
import Card, { CardBody, CardHeader } from '../components/ui/Card';

const ACCESS_LEVELS = [
  {
    value: 'level_1',
    label: 'General — level 1',
    description: 'All authenticated users',
  },
  {
    value: 'level_2',
    label: 'Legal team — level 2',
    description: 'Admin and owner only',
  },
  {
    value: 'level_3',
    label: 'Privileged — level 3',
    description: 'Owner only',
  },
];

export default function Upload() {
  const [files, setFiles] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState({});
  const [accessLevel, setAccessLevel] = useState('level_1');

  const handleDrop = (e) => {
    e.preventDefault();
    const droppedFiles = Array.from(e.dataTransfer.files).filter(f => f.type === 'application/pdf');
    if (droppedFiles.length === 0) {
      toast.error('Only PDF files are supported');
      return;
    }
    setFiles(prev => [...prev, ...droppedFiles]);
    toast.success(`Added ${droppedFiles.length} file(s)`);
  };

  const handleFileInput = (e) => {
    const selectedFiles = Array.from(e.target.files || []).filter(f => f.type === 'application/pdf');
    if (selectedFiles.length === 0) {
      toast.error('Only PDF files are supported');
      return;
    }
    setFiles(prev => [...prev, ...selectedFiles]);
    toast.success(`Added ${selectedFiles.length} file(s)`);
  };

  const removeFile = (index) => {
    setFiles(prev => prev.filter((_, i) => i !== index));
  };

  const handleUpload = async () => {
    if (files.length === 0) {
      toast.error('Please select at least one file');
      return;
    }

    setUploading(true);
    let uploadedCount = 0;
    let failedCount = 0;

    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      setUploadProgress(prev => ({ ...prev, [i]: 'uploading' }));

      try {
        console.log(`📤 Uploading file ${i + 1}/${files.length}:`, file.name, 'access_level:', accessLevel);
        await uploadAPI.upload(file, accessLevel);
        setUploadProgress(prev => ({ ...prev, [i]: 'success' }));
        uploadedCount++;
        toast.success(`✅ ${file.name} uploaded`, { duration: 2000 });
      } catch (error) {
        console.error(`❌ Upload failed for ${file.name}:`, error);
        let errorMsg = 'Upload failed';
        if (error.response?.status === 429) {
          errorMsg = 'Rate limited — too many uploads. Please wait.';
        } else if (error.response?.status === 401) {
          errorMsg = 'Session expired. Please log in again.';
        } else if (error.response?.status === 403) {
          errorMsg = 'Insufficient permissions for this access level.';
        } else if (error.response?.data?.detail) {
          errorMsg = error.response.data.detail;
        } else if (error.message) {
          errorMsg = error.message;
        }
        setUploadProgress(prev => ({ ...prev, [i]: 'error' }));
        failedCount++;
        toast.error(`❌ ${file.name}: ${errorMsg}`, { duration: 4000 });
      }
    }

    setUploading(false);

    if (uploadedCount > 0 && failedCount === 0) {
      toast.success(`🎉 All ${uploadedCount} file(s) uploaded successfully!`);
      setFiles([]);
      setUploadProgress({});
    } else if (uploadedCount > 0) {
      toast(`✓ ${uploadedCount} uploaded, ✗ ${failedCount} failed`, { icon: '⚠️' });
    } else {
      toast.error(`Failed to upload ${failedCount} file(s)`);
    }
  };

  const selectedLevel = ACCESS_LEVELS.find(l => l.value === accessLevel);

  return (
    <div className="min-h-screen bg-neutral-50 py-8 px-4">
      <div className="max-w-4xl mx-auto">
        <div className="mb-8">
          <h1 className="text-3xl md:text-4xl font-bold text-neutral-900 mb-2">Upload Documents</h1>
          <p className="text-neutral-600">Upload PDF documents for BEWEIS to analyze and reference</p>
        </div>

        {/* Access Level Selector */}
        <Card className="mb-6">
          <CardHeader>
            <div className="flex items-center gap-2">
              <Lock className="w-4 h-4 text-neutral-500" />
              <h3 className="font-semibold text-neutral-900">Document clearance level</h3>
            </div>
          </CardHeader>
          <CardBody>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              {ACCESS_LEVELS.map((level) => (
                <button
                  key={level.value}
                  type="button"
                  onClick={() => setAccessLevel(level.value)}
                  disabled={uploading}
                  className={[
                    'text-left p-4 rounded-lg border-2 transition-all',
                    accessLevel === level.value
                      ? 'border-primary-600 bg-primary-50'
                      : 'border-neutral-200 hover:border-neutral-300 bg-white',
                    'disabled:opacity-50 disabled:cursor-not-allowed'
                  ].join(' ')}
                >
                  <p className={[
                    'text-sm font-semibold',
                    accessLevel === level.value ? 'text-primary-700' : 'text-neutral-900'
                  ].join(' ')}>
                    {level.label}
                  </p>
                  <p className="text-xs text-neutral-500 mt-1">{level.description}</p>
                </button>
              ))}
            </div>
            {accessLevel !== 'level_1' && (
              <p className="text-xs text-amber-600 mt-3">
                ⚠ This document will be restricted — only users with sufficient clearance will see it in query results.
              </p>
            )}
          </CardBody>
        </Card>

        {/* Upload Zone */}
        <Card className="mb-6">
          <CardBody
            onDragOver={(e) => e.preventDefault()}
            onDrop={handleDrop}
            className="border-2 border-dashed border-neutral-300 hover:border-primary-500 rounded-lg p-12 text-center transition-colors cursor-pointer"
          >
            <UploadIcon className="w-12 h-12 text-neutral-400 mx-auto mb-4" />
            <h3 className="text-xl font-semibold text-neutral-900 mb-2">Drag and drop your files</h3>
            <p className="text-neutral-600 mb-6">PDF files only · Max 50MB</p>
            <label>
              <input
                type="file"
                multiple
                accept=".pdf"
                onChange={handleFileInput}
                disabled={uploading}
                className="hidden"
              />
              <Button
                variant="secondary"
                disabled={uploading}
                onClick={(e) => {
                  e.preventDefault();
                  e.currentTarget.parentElement.querySelector('input').click();
                }}
              >
                Browse Files
              </Button>
            </label>
          </CardBody>
        </Card>

        {/* Files List */}
        {files.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="mb-6"
          >
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <h3 className="text-lg font-semibold text-neutral-900">Selected Files ({files.length})</h3>
                  <span className="text-xs text-neutral-500 bg-neutral-100 px-2 py-1 rounded">
                    {selectedLevel?.label}
                  </span>
                </div>
              </CardHeader>
              <CardBody className="divide-y divide-neutral-200">
                {files.map((file, idx) => (
                  <div key={idx} className="flex items-center justify-between py-3 first:pt-0 last:pb-0">
                    <div className="flex items-center gap-3 flex-1 min-w-0">
                      <File className="w-5 h-5 text-primary-600 flex-shrink-0" />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm text-neutral-900 truncate">{file.name}</p>
                        <p className="text-xs text-neutral-600">{(file.size / 1024 / 1024).toFixed(2)} MB</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-3 ml-2">
                      {uploadProgress[idx] === 'success' && (
                        <div className="flex items-center gap-1 text-success-600">
                          <CheckCircle className="w-5 h-5" />
                          <span className="text-sm">Done</span>
                        </div>
                      )}
                      {uploadProgress[idx] === 'error' && (
                        <div className="flex items-center gap-1 text-danger-600">
                          <AlertCircle className="w-5 h-5" />
                          <span className="text-sm">Failed</span>
                        </div>
                      )}
                      {uploadProgress[idx] === 'uploading' && (
                        <div className="w-24 h-1.5 bg-neutral-200 rounded-full overflow-hidden">
                          <div className="h-full bg-primary-600 animate-pulse w-2/3"></div>
                        </div>
                      )}
                      {!uploadProgress[idx] && (
                        <button
                          type="button"
                          onClick={() => removeFile(idx)}
                          disabled={uploading}
                          className="p-1 text-neutral-400 hover:text-danger-600 disabled:opacity-50 transition-colors"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </CardBody>
            </Card>
          </motion.div>
        )}

        {files.length > 0 && (
          <Button
            onClick={handleUpload}
            disabled={uploading}
            loading={uploading}
            className="w-full"
            size="lg"
          >
            {uploading
              ? <>Uploading {files.length} file{files.length !== 1 ? 's' : ''}...</>
              : <>Upload {files.length} file{files.length !== 1 ? 's' : ''} as {selectedLevel?.label}</>
            }
          </Button>
        )}
      </div>
    </div>
  );
}
