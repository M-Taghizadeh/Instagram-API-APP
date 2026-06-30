const DATA_KEYS = new Set(['nodeType', 'isStart', 'label']);

export function newNodeId() {
  return crypto.randomUUID().replace(/-/g, '').slice(0, 8);
}

export function defaultDataForType(type) {
  const defaults = {
    text: { text: 'پیام متنی...' },
    image: { url: '' },
    video: { url: '' },
    audio: { url: '' },
    carousel: {
      elements: [{
        title: 'محصول ۱',
        subtitle: '',
        image_url: '',
        url: '',
        buttons: [{ title: 'مشاهده', type: 'url', url: 'https://example.com' }],
      }],
    },
    buttons: { text: 'انتخاب کنید:', buttons: [{ title: 'گزینه ۱', type: 'postback', payload: 'opt1' }] },
    quick_replies: { text: 'یک گزینه انتخاب کنید:', options: [] },
    collect_phone: { prompt: 'شماره تماس؟', field: 'phone' },
    collect_text: { prompt: 'پاسخ شما؟', field: 'answer' },
    poll: { question: 'نظرسنجی:', field: 'poll_answer', options: [{ title: 'گزینه ۱' }] },
    quiz: {
      question: 'سوال آزمون؟',
      field: 'quiz_score',
      options: [{ title: 'پاسخ ۱', payload: 'a1' }],
      correct: { answer: 'a1', values: ['a1'] },
    },
    delay: { minutes: 60, followup_payload: { type: 'text', text: 'پیام فالوآپ' } },
    save_contact: {},
    comment_reply: { text: 'پاسخ کامنت' },
    dm: { text: 'پیام دایرکت' },
  };
  return { ...(defaults[type] || { text: '' }) };
}

export function toReactFlow(flowNodes) {
  const nodes = (flowNodes || []).map((n, i) => ({
    id: n.id,
    type: 'flowNode',
    position: n.position || { x: 280, y: i * 130 + 40 },
    data: {
      nodeType: n.type || 'text',
      isStart: Boolean(n.is_start),
      ...structuredClone(n.data || {}),
    },
  }));

  const edges = [];
  (flowNodes || []).forEach((n) => {
    if (n.next) {
      edges.push({
        id: `e-${n.id}-${n.next}`,
        source: n.id,
        target: n.next,
        type: 'smoothstep',
        animated: true,
      });
    }
    if (n.branches) {
      Object.entries(n.branches).forEach(([branch, target]) => {
        if (!target) return;
        edges.push({
          id: `e-${n.id}-${branch}-${target}`,
          source: n.id,
          target,
          sourceHandle: branch,
          label: branch,
          type: 'smoothstep',
        });
      });
    }
  });

  return { nodes, edges };
}

function pickNodeData(data) {
  const out = {};
  Object.entries(data || {}).forEach(([k, v]) => {
    if (!DATA_KEYS.has(k)) out[k] = v;
  });
  return out;
}

export function fromReactFlow(rfNodes, edges) {
  const hasStart = rfNodes.some((n) => n.data?.isStart);
  return rfNodes.map((n, i) => {
    const mainEdge = edges.find((e) => e.source === n.id && !e.sourceHandle);
    const branchEdges = edges.filter((e) => e.source === n.id && e.sourceHandle);
    const item = {
      id: n.id,
      type: n.data?.nodeType || 'text',
      data: pickNodeData(n.data),
      next: mainEdge?.target || '',
      position: { x: Math.round(n.position.x), y: Math.round(n.position.y) },
    };
    if (n.data?.isStart || (!hasStart && i === 0)) {
      item.is_start = true;
    }
    if (branchEdges.length) {
      item.branches = Object.fromEntries(
        branchEdges.map((e) => [e.sourceHandle, e.target])
      );
    }
    return item;
  });
}
