export const NODE_TYPES = [
  { type: 'text', icon: '💬', label: 'متن' },
  { type: 'image', icon: '🖼️', label: 'تصویر' },
  { type: 'audio', icon: '🎵', label: 'صوت' },
  { type: 'carousel', icon: '🛍️', label: 'ویترین' },
  { type: 'buttons', icon: '🔘', label: 'دکمه‌ها' },
  { type: 'collect_text', icon: '✏️', label: 'دریافت متن' },
  { type: 'collect_phone', icon: '📱', label: 'دریافت شماره' },
  { type: 'poll', icon: '📊', label: 'نظرسنجی' },
  { type: 'quiz', icon: '🎯', label: 'آزمون' },
  { type: 'delay', icon: '⏱️', label: 'تأخیر' },
  { type: 'save_contact', icon: '💾', label: 'ذخیره مخاطب' },
];

export function metaFor(type) {
  return NODE_TYPES.find((n) => n.type === type) || { type, icon: '◆', label: type };
}

export function previewText(nodeType, data) {
  switch (nodeType) {
    case 'text':
      return data.text || '';
    case 'collect_text':
    case 'collect_phone':
      return data.prompt || '';
    case 'poll':
      return `${data.question || ''} (${(data.options || []).length} گزینه)`;
    case 'quiz':
      return `${data.question || ''} (${(data.options || []).length} پاسخ)`;
    case 'delay': {
      const fp = data.followup_payload || {};
      const msg = fp.text || (fp.type === 'image' ? 'تصویر' : fp.type === 'audio' ? 'صوت' : '');
      return `${data.minutes || 0} دقیقه — ${msg || 'فالوآپ'}`;
    }
    case 'save_contact':
      return 'ذخیره در مخاطبین';
    case 'image':
      return data.url ? 'تصویر' : 'بدون تصویر';
    case 'video':
      return data.url ? 'ویدیو' : 'بدون ویدیو';
    case 'audio':
      return data.url ? 'صوت' : 'بدون صوت';
    case 'carousel':
      return `${(data.elements || []).length} آیتم ویترین`;
    case 'buttons':
      return data.text || `${(data.buttons || []).length} دکمه`;
    default:
      return data.text || data.question || '';
  }
}
