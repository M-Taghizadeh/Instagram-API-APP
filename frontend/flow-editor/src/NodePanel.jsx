import { metaFor } from './nodeMeta';

function Field({ label, children }) {
  return (
    <label className="fe-field">
      <span>{label}</span>
      {children}
    </label>
  );
}

export default function NodePanel({ node, onChange, onDelete, onSetStart }) {
  if (!node) {
    return (
      <div className="fe-panel fe-panel-empty">
        <p>یک نود انتخاب کنید یا از پالت نود جدید اضافه کنید.</p>
      </div>
    );
  }

  const { nodeType, isStart, ...data } = node.data;
  const meta = metaFor(nodeType);

  const setData = (key, value) => {
    onChange(node.id, { ...node.data, [key]: value });
  };

  return (
    <div className="fe-panel">
      <div className="fe-panel-title">
        <span>{meta.icon}</span> {meta.label}
      </div>

      <label className="fe-check">
        <input
          type="checkbox"
          checked={Boolean(isStart)}
          onChange={(e) => onSetStart(node.id, e.target.checked)}
        />
        نود شروع فلو
      </label>

      {(nodeType === 'text' || nodeType === 'dm' || nodeType === 'comment_reply') && (
        <Field label="متن پیام">
          <textarea
            rows={4}
            value={data.text || ''}
            onChange={(e) => setData('text', e.target.value)}
          />
        </Field>
      )}

      {(nodeType === 'collect_text' || nodeType === 'collect_phone') && (
        <>
          <Field label="سوال / پرامپت">
            <textarea
              rows={3}
              value={data.prompt || ''}
              onChange={(e) => setData('prompt', e.target.value)}
            />
          </Field>
          <Field label="نام فیلد">
            <input
              type="text"
              value={data.field || ''}
              onChange={(e) => setData('field', e.target.value)}
            />
          </Field>
        </>
      )}

      {(nodeType === 'poll' || nodeType === 'quiz') && (
        <Field label="سوال">
          <textarea
            rows={3}
            value={data.question || ''}
            onChange={(e) => setData('question', e.target.value)}
          />
        </Field>
      )}

      {nodeType === 'delay' && (
        <Field label="تأخیر (دقیقه)">
          <input
            type="number"
            min={1}
            value={data.minutes ?? 60}
            onChange={(e) => setData('minutes', Number(e.target.value))}
          />
        </Field>
      )}

      {(nodeType === 'image' || nodeType === 'video' || nodeType === 'audio') && (
        <Field label="URL مدیا">
          <input
            type="text"
            dir="ltr"
            value={data.url || ''}
            onChange={(e) => setData('url', e.target.value)}
          />
        </Field>
      )}

      {nodeType === 'carousel' && (
        <Field label="عناصر ویترین (JSON)">
          <textarea
            rows={8}
            dir="ltr"
            value={JSON.stringify(data.elements || [], null, 2)}
            onChange={(e) => {
              try {
                const elements = JSON.parse(e.target.value || '[]');
                if (Array.isArray(elements)) setData('elements', elements);
              } catch {
                /* ignore while typing */
              }
            }}
          />
        </Field>
      )}

      {nodeType === 'save_contact' && (
        <p className="fe-hint">اطلاعات جمع‌آوری‌شده در مخاطبین ذخیره می‌شود.</p>
      )}

      <button type="button" className="fe-btn-danger" onClick={() => onDelete(node.id)}>
        حذف نود
      </button>
    </div>
  );
}
