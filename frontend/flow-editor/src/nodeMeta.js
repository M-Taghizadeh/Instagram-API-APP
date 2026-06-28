export const NODE_TYPES = [
  { type: 'text', icon: '💬', label: 'متن' },
  { type: 'image', icon: '🖼️', label: 'تصویر' },
  { type: 'video', icon: '🎬', label: 'ویدیو' },
  { type: 'audio', icon: '🎵', label: 'صوت' },
  { type: 'carousel', icon: '🛍️', label: 'ویترین' },
  { type: 'buttons', icon: '🔘', label: 'دکمه‌ها' },
  { type: 'quick_replies', icon: '⚡', label: 'پاسخ سریع' },
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
    case 'quiz':
      return data.question || '';
    case 'delay':
      return `${data.minutes || 0} دقیقه`;
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
    default:
      return data.text || data.question || '';
  }
}
