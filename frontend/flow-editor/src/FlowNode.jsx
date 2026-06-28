import { memo } from 'react';
import { Handle, Position } from '@xyflow/react';
import { metaFor, previewText } from './nodeMeta';

function shortUrl(url) {
  try {
    const u = new URL(url);
    const tail = u.pathname.split('/').pop() || u.hostname;
    return tail.length > 22 ? `${tail.slice(0, 20)}…` : tail;
  } catch {
    return url.length > 22 ? `${url.slice(0, 20)}…` : url;
  }
}

function FlowNode({ data, selected }) {
  const meta = metaFor(data.nodeType);
  const preview = previewText(data.nodeType, data);

  return (
    <div className={`fe-node ${selected ? 'selected' : ''} ${data.isStart ? 'is-start' : ''}`}>
      <Handle type="target" position={Position.Top} className="fe-handle" />
      <div className="fe-node-head">
        <span className="fe-node-icon">{meta.icon}</span>
        <span className="fe-node-type">{meta.label}</span>
        {data.isStart && <span className="fe-start-badge">شروع</span>}
      </div>
      <div className="fe-node-body">
        {data.nodeType === 'image' && data.url ? (
          <img src={data.url} alt="" className="fe-node-media-preview" />
        ) : data.nodeType === 'video' && data.url ? (
          <div className="fe-node-media-tag">ویدیو · {shortUrl(data.url)}</div>
        ) : data.nodeType === 'audio' && data.url ? (
          <div className="fe-node-media-tag">صوت · {shortUrl(data.url)}</div>
        ) : (
          <div className="fe-node-preview">{preview || '—'}</div>
        )}
      </div>
      <Handle type="source" position={Position.Bottom} className="fe-handle" />
    </div>
  );
}

export default memo(FlowNode);
