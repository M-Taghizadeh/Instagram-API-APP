import { memo } from 'react';
import { Handle, Position } from '@xyflow/react';
import { metaFor, previewText } from './nodeMeta';

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
      <div className="fe-node-preview">{preview || '—'}</div>
      <Handle type="source" position={Position.Bottom} className="fe-handle" />
    </div>
  );
}

export default memo(FlowNode);
