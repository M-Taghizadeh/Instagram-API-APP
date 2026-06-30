import MediaField from './MediaField';

export function HintBox({ children }) {
  return <p className="fe-hint">{children}</p>;
}

function ListActions({ onAdd, addLabel, count, max }) {
  return (
    <div className="fe-list-actions">
      <span className="fe-list-count">{count} / {max}</span>
      {count < max && (
        <button type="button" className="fe-btn-add" onClick={onAdd}>
          + {addLabel}
        </button>
      )}
    </div>
  );
}

function RemoveBtn({ onClick }) {
  return (
    <button type="button" className="fe-btn-remove" onClick={onClick} title="حذف">
      ×
    </button>
  );
}

export function ButtonListEditor({ buttons = [], onChange, max = 3 }) {
  const update = (idx, patch) => {
    const next = buttons.map((b, i) => (i === idx ? { ...b, ...patch } : b));
    onChange(next);
  };

  const add = () => {
    if (buttons.length >= max) return;
    onChange([...buttons, { title: 'دکمه جدید', type: 'postback', payload: 'btn' }]);
  };

  const remove = (idx) => onChange(buttons.filter((_, i) => i !== idx));

  return (
    <div className="fe-list-editor">
      {buttons.map((btn, i) => (
        <div key={i} className="fe-list-item">
          <div className="fe-list-item-head">
            <span>دکمه {i + 1}</span>
            <RemoveBtn onClick={() => remove(i)} />
          </div>
          <label className="fe-inline-field">
            <span>عنوان</span>
            <input
              type="text"
              value={btn.title || ''}
              onChange={(e) => update(i, { title: e.target.value })}
              maxLength={20}
            />
          </label>
          <label className="fe-inline-field">
            <span>نوع</span>
            <select
              value={btn.type === 'url' ? 'url' : 'postback'}
              onChange={(e) => update(i, { type: e.target.value })}
            >
              <option value="postback">پاسخ در چت</option>
              <option value="url">لینک وب</option>
            </select>
          </label>
          {btn.type === 'url' ? (
            <label className="fe-inline-field">
              <span>آدرس لینک</span>
              <input
                type="url"
                dir="ltr"
                value={btn.url || ''}
                onChange={(e) => update(i, { url: e.target.value })}
                placeholder="https://..."
              />
            </label>
          ) : (
            <label className="fe-inline-field">
              <span>شناسه پاسخ (payload)</span>
              <input
                type="text"
                dir="ltr"
                value={btn.payload || ''}
                onChange={(e) => update(i, { payload: e.target.value })}
              />
            </label>
          )}
        </div>
      ))}
      <ListActions onAdd={add} addLabel="دکمه" count={buttons.length} max={max} />
    </div>
  );
}

export function PollOptionsEditor({ options = [], onChange, max = 13 }) {
  const update = (idx, title) => {
    const next = options.map((o, i) =>
      i === idx ? { ...o, title, payload: o.payload ?? String(i) } : o
    );
    onChange(next);
  };

  const add = () => {
    if (options.length >= max) return;
    const n = options.length + 1;
    onChange([...options, { title: `گزینه ${n}`, payload: String(options.length) }]);
  };

  const remove = (idx) => onChange(options.filter((_, i) => i !== idx));

  return (
    <div className="fe-list-editor">
      {options.map((opt, i) => (
        <div key={i} className="fe-list-item fe-list-item-compact">
          <div className="fe-list-item-head">
            <span>گزینه {i + 1}</span>
            <RemoveBtn onClick={() => remove(i)} />
          </div>
          <input
            type="text"
            value={opt.title || ''}
            onChange={(e) => update(i, e.target.value)}
            maxLength={20}
            placeholder="متن گزینه"
          />
        </div>
      ))}
      <ListActions onAdd={add} addLabel="گزینه" count={options.length} max={max} />
    </div>
  );
}

export function QuizOptionsEditor({ options = [], correct = {}, onChangeOptions, onChangeCorrect }) {
  const correctAnswer = correct.answer || (options[0]?.payload ?? '');

  const updateOption = (idx, patch) => {
    const next = options.map((o, i) => (i === idx ? { ...o, ...patch } : o));
    onChangeOptions(next);
  };

  const add = () => {
    if (options.length >= 13) return;
    const id = `opt${options.length + 1}`;
    onChangeOptions([...options, { title: `پاسخ ${options.length + 1}`, payload: id }]);
  };

  const remove = (idx) => {
    const removed = options[idx];
    const next = options.filter((_, i) => i !== idx);
    onChangeOptions(next);
    if (removed?.payload === correctAnswer && next.length) {
      onChangeCorrect({ ...correct, answer: next[0].payload, values: [next[0].payload] });
    }
  };

  const setCorrect = (payload) => {
    const opt = options.find((o) => o.payload === payload);
    onChangeCorrect({
      answer: payload,
      values: [payload, opt?.title].filter(Boolean),
    });
  };

  return (
    <div className="fe-list-editor">
      {options.map((opt, i) => (
        <div key={i} className="fe-list-item">
          <div className="fe-list-item-head">
            <label className="fe-correct-radio">
              <input
                type="radio"
                name="quiz-correct"
                checked={opt.payload === correctAnswer}
                onChange={() => setCorrect(opt.payload)}
              />
              <span>پاسخ صحیح</span>
            </label>
            <RemoveBtn onClick={() => remove(i)} />
          </div>
          <label className="fe-inline-field">
            <span>متن پاسخ</span>
            <input
              type="text"
              value={opt.title || ''}
              onChange={(e) => updateOption(i, { title: e.target.value })}
              maxLength={20}
            />
          </label>
          <label className="fe-inline-field">
            <span>شناسه (payload)</span>
            <input
              type="text"
              dir="ltr"
              value={opt.payload || ''}
              onChange={(e) => {
                const oldPayload = opt.payload;
                const newPayload = e.target.value;
                updateOption(i, { payload: newPayload });
                if (oldPayload === correctAnswer) {
                  onChangeCorrect({ ...correct, answer: newPayload, values: [newPayload, opt.title] });
                }
              }}
            />
          </label>
        </div>
      ))}
      <ListActions onAdd={add} addLabel="پاسخ" count={options.length} max={13} />
    </div>
  );
}

export function CarouselElementsEditor({ elements = [], onChange }) {
  const update = (idx, patch) => {
    onChange(elements.map((el, i) => (i === idx ? { ...el, ...patch } : el)));
  };

  const updateButtons = (idx, buttons) => {
    update(idx, { buttons });
  };

  const add = () => {
    if (elements.length >= 10) return;
    onChange([
      ...elements,
      {
        title: `محصول ${elements.length + 1}`,
        subtitle: '',
        image_url: '',
        url: '',
        buttons: [],
      },
    ]);
  };

  const remove = (idx) => onChange(elements.filter((_, i) => i !== idx));

  return (
    <div className="fe-list-editor">
      {elements.map((el, i) => (
        <div key={i} className="fe-list-item fe-list-item-wide">
          <div className="fe-list-item-head">
            <span>آیتم {i + 1}</span>
            <RemoveBtn onClick={() => remove(i)} />
          </div>
          <label className="fe-inline-field">
            <span>عنوان</span>
            <input
              type="text"
              value={el.title || ''}
              onChange={(e) => update(i, { title: e.target.value })}
              maxLength={80}
            />
          </label>
          <label className="fe-inline-field">
            <span>زیرعنوان</span>
            <input
              type="text"
              value={el.subtitle || ''}
              onChange={(e) => update(i, { subtitle: e.target.value })}
              maxLength={80}
            />
          </label>
          <label className="fe-inline-field">
            <span>تصویر</span>
            <MediaField
              mediaType="image"
              url={el.image_url || ''}
              onChange={(url) => update(i, { image_url: url })}
            />
          </label>
          <label className="fe-inline-field">
            <span>لینک کلیک روی کارت</span>
            <input
              type="url"
              dir="ltr"
              value={el.url || ''}
              onChange={(e) => update(i, { url: e.target.value })}
              placeholder="https://..."
            />
          </label>
          <div className="fe-subsection">
            <span className="fe-subsection-title">دکمه‌های کارت</span>
            <ButtonListEditor
              buttons={el.buttons || []}
              onChange={(buttons) => updateButtons(i, buttons)}
              max={3}
            />
          </div>
        </div>
      ))}
      <ListActions onAdd={add} addLabel="آیتم ویترین" count={elements.length} max={10} />
    </div>
  );
}

const FOLLOWUP_TYPES = [
  { value: 'text', label: 'متن' },
  { value: 'image', label: 'تصویر' },
  { value: 'audio', label: 'صوت' },
];

export function FollowupPayloadEditor({ payload = {}, onChange }) {
  const type = payload.type || 'text';

  const setType = (newType) => {
    if (newType === 'text') onChange({ type: 'text', text: payload.text || 'پیام فالوآپ' });
    else if (newType === 'image') onChange({ type: 'image', url: payload.url || '' });
    else onChange({ type: 'audio', url: payload.url || '' });
  };

  return (
    <div className="fe-followup-editor">
      <label className="fe-inline-field">
        <span>نوع پیام فالوآپ</span>
        <select value={type} onChange={(e) => setType(e.target.value)}>
          {FOLLOWUP_TYPES.map((t) => (
            <option key={t.value} value={t.value}>{t.label}</option>
          ))}
        </select>
      </label>
      {type === 'text' && (
        <label className="fe-inline-field">
          <span>متن پیام</span>
          <textarea
            rows={3}
            value={payload.text || ''}
            onChange={(e) => onChange({ ...payload, type: 'text', text: e.target.value })}
          />
        </label>
      )}
      {(type === 'image' || type === 'audio') && (
        <label className="fe-inline-field">
          <span>{type === 'image' ? 'تصویر' : 'فایل صوتی'}</span>
          <MediaField
            mediaType={type}
            url={payload.url || ''}
            onChange={(url) => onChange({ ...payload, type, url })}
          />
        </label>
      )}
    </div>
  );
}
