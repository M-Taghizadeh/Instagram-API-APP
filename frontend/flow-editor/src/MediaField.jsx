import { useRef, useState } from 'react';

const ACCEPT = {
  image: 'image/png,image/jpeg,image/gif,image/webp',
  video: 'video/mp4,video/quicktime,video/webm,video/x-msvideo',
  audio: 'audio/mpeg,audio/wav,audio/mp4,audio/aac,audio/ogg',
};

async function uploadFile(file, mediaType) {
  const fd = new FormData();
  fd.append('file', file);
  fd.append('type', mediaType);
  const res = await fetch('/media/upload', { method: 'POST', body: fd, credentials: 'same-origin' });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || 'خطا در آپلود فایل');
  return data.url;
}

export default function MediaField({ mediaType, url, onChange }) {
  const inputRef = useRef(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');

  const handleFile = async (file) => {
    if (!file) return;
    setError('');
    setUploading(true);
    try {
      const uploadedUrl = await uploadFile(file, mediaType);
      onChange(uploadedUrl);
    } catch (e) {
      setError(e.message || 'آپلود ناموفق بود');
    } finally {
      setUploading(false);
      if (inputRef.current) inputRef.current.value = '';
    }
  };

  const onPick = (e) => handleFile(e.target.files?.[0]);
  const onDrop = (e) => {
    e.preventDefault();
    handleFile(e.dataTransfer.files?.[0]);
  };

  return (
    <div className="fe-media-field">
      {url && mediaType === 'image' && (
        <img src={url} alt="" className="fe-media-preview" />
      )}
      {url && mediaType === 'video' && (
        <video src={url} className="fe-media-preview" controls preload="metadata" />
      )}
      {url && mediaType === 'audio' && (
        <audio src={url} className="fe-media-audio" controls preload="metadata" />
      )}

      <div
        className={`fe-media-drop${uploading ? ' is-uploading' : ''}`}
        onClick={() => !uploading && inputRef.current?.click()}
        onDragOver={(e) => e.preventDefault()}
        onDrop={onDrop}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => e.key === 'Enter' && inputRef.current?.click()}
      >
        {uploading ? 'در حال آپلود…' : 'کلیک یا فایل را اینجا رها کنید'}
      </div>
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPT[mediaType]}
        onChange={onPick}
        hidden
      />

      <input
        type="text"
        dir="ltr"
        className="fe-media-url"
        placeholder="یا URL مستقیم مدیا"
        value={url || ''}
        onChange={(e) => onChange(e.target.value)}
      />

      {error && <p className="fe-media-error">{error}</p>}
    </div>
  );
}
