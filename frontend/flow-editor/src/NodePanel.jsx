import { metaFor } from './nodeMeta';
import MediaField from './MediaField';
import {
  HintBox,
  ButtonListEditor,
  PollOptionsEditor,
  QuizOptionsEditor,
  CarouselElementsEditor,
  FollowupPayloadEditor,
} from './OptionEditors';

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

      {nodeType === 'collect_text' && (
        <>
          <HintBox>
            از کاربر یک پاسخ متنی می‌گیرد (مثل نام، ایمیل یا هر سوال آزاد).
            پاسخ در فلو ذخیره می‌شود و با نود «ذخیره مخاطب» در لیست مخاطبین ثبت می‌شود.
          </HintBox>
          <Field label="سوال از کاربر">
            <textarea
              rows={3}
              value={data.prompt || ''}
              onChange={(e) => setData('prompt', e.target.value)}
              placeholder="مثلاً: نام کامل شما چیست؟"
            />
          </Field>
          <Field label="نام فیلد (برای ذخیره)">
            <input
              type="text"
              dir="ltr"
              value={data.field || ''}
              onChange={(e) => setData('field', e.target.value)}
              placeholder="full_name"
            />
          </Field>
          <HintBox>
            فیلدهای شناخته‌شده: full_name، email — بقیه در فیلدهای سفارشی مخاطب ذخیره می‌شوند.
          </HintBox>
        </>
      )}

      {nodeType === 'collect_phone' && (
        <>
          <HintBox>
            از کاربر شماره تماس می‌گیرد. شماره در فلو ذخیره و هنگام «ذخیره مخاطب»
            در فیلد phone مخاطب ثبت می‌شود.
          </HintBox>
          <Field label="سوال از کاربر">
            <textarea
              rows={3}
              value={data.prompt || ''}
              onChange={(e) => setData('prompt', e.target.value)}
              placeholder="مثلاً: شماره تماس خود را بفرستید"
            />
          </Field>
          <Field label="نام فیلد">
            <input
              type="text"
              dir="ltr"
              value={data.field || 'phone'}
              onChange={(e) => setData('field', e.target.value)}
            />
          </Field>
        </>
      )}

      {nodeType === 'poll' && (
        <>
          <HintBox>
            نظرسنجی با دکمه‌های سریع اینستاگرام. کاربر یک گزینه انتخاب می‌کند و فلو ادامه پیدا می‌کند.
          </HintBox>
          <Field label="سوال نظرسنجی">
            <textarea
              rows={3}
              value={data.question || ''}
              onChange={(e) => setData('question', e.target.value)}
            />
          </Field>
          <Field label="گزینه‌ها">
            <PollOptionsEditor
              options={data.options || []}
              onChange={(options) => setData('options', options)}
            />
          </Field>
          <Field label="نام فیلد (ذخیره پاسخ)">
            <input
              type="text"
              dir="ltr"
              value={data.field || 'poll_answer'}
              onChange={(e) => setData('field', e.target.value)}
            />
          </Field>
        </>
      )}

      {nodeType === 'quiz' && (
        <>
          <HintBox>
            سوال چندگزینه‌ای با امتیازدهی. پاسخ صحیح را مشخص کنید؛
            اگر کاربر درست جواب دهد امتیاز ۱ و در غیر این صورت ۰ ذخیره می‌شود.
          </HintBox>
          <Field label="سوال آزمون">
            <textarea
              rows={3}
              value={data.question || ''}
              onChange={(e) => setData('question', e.target.value)}
            />
          </Field>
          <Field label="گزینه‌های پاسخ">
            <QuizOptionsEditor
              options={data.options || []}
              correct={data.correct || {}}
              onChangeOptions={(options) => setData('options', options)}
              onChangeCorrect={(correct) => setData('correct', correct)}
            />
          </Field>
          <Field label="نام فیلد (ذخیره امتیاز)">
            <input
              type="text"
              dir="ltr"
              value={data.field || 'quiz_score'}
              onChange={(e) => setData('field', e.target.value)}
            />
          </Field>
        </>
      )}

      {nodeType === 'delay' && (
        <>
          <HintBox>
            فلو را متوقف می‌کند و پس از مدت مشخص، پیام فالوآپ را برای کاربر ارسال می‌کند.
          </HintBox>
          <Field label="تأخیر (دقیقه)">
            <input
              type="number"
              min={1}
              value={data.minutes ?? 60}
              onChange={(e) => setData('minutes', Number(e.target.value))}
            />
          </Field>
          <Field label="پیام فالوآپ">
            <FollowupPayloadEditor
              payload={data.followup_payload || { type: 'text', text: 'پیام فالوآپ' }}
              onChange={(followup_payload) => setData('followup_payload', followup_payload)}
            />
          </Field>
        </>
      )}

      {(nodeType === 'image' || nodeType === 'audio') && (
        <Field label={nodeType === 'image' ? 'تصویر' : 'صوت'}>
          <MediaField
            mediaType={nodeType}
            url={data.url || ''}
            onChange={(value) => setData('url', value)}
          />
        </Field>
      )}

      {nodeType === 'video' && (
        <p className="fe-hint">نود ویدیو دیگر پشتیبانی نمی‌شود. این نود را حذف کنید.</p>
      )}

      {nodeType === 'buttons' && (
        <>
          <HintBox>
            پیام با دکمه‌های قابل کلیک (حداکثر ۳ دکمه). می‌تواند لینک وب یا پاسخ در چت باشد.
          </HintBox>
          <Field label="متن پیام">
            <textarea
              rows={3}
              value={data.text || ''}
              onChange={(e) => setData('text', e.target.value)}
            />
          </Field>
          <Field label="دکمه‌ها">
            <ButtonListEditor
              buttons={data.buttons || []}
              onChange={(buttons) => setData('buttons', buttons)}
            />
          </Field>
        </>
      )}

      {nodeType === 'carousel' && (
        <>
          <HintBox>
            ویترین محصولات — کارت‌های اسکرول‌شونده با تصویر، عنوان و دکمه (حداکثر ۱۰ آیتم).
          </HintBox>
          <Field label="آیتم‌های ویترین">
            <CarouselElementsEditor
              elements={data.elements || []}
              onChange={(elements) => setData('elements', elements)}
            />
          </Field>
        </>
      )}

      {nodeType === 'save_contact' && (
        <>
          <HintBox>
            اطلاعات جمع‌آوری‌شده از نودهای «دریافت متن» و «دریافت شماره» را در مخاطبین ذخیره می‌کند.
            معمولاً بعد از جمع‌آوری اطلاعات در فلو قرار می‌گیرد.
          </HintBox>
          <div className="fe-info-box">
            <strong>نمونه ترتیب فلو:</strong>
            <ol>
              <li>دریافت متن (نام)</li>
              <li>دریافت شماره</li>
              <li>ذخیره مخاطب ← این نود</li>
              <li>پیام تشکر</li>
            </ol>
          </div>
        </>
      )}

      {nodeType === 'quick_replies' && (
        <HintBox>
          این نود قدیمی است. برای نظرسنجی از نود «نظرسنجی» و برای دکمه از نود «دکمه‌ها» استفاده کنید.
        </HintBox>
      )}

      <button type="button" className="fe-btn-danger" onClick={() => onDelete(node.id)}>
        حذف نود
      </button>
    </div>
  );
}
