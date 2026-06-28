import { createRef } from 'react';
import { createRoot } from 'react-dom/client';
import FlowEditor from './FlowEditor';
import './editor.css';

function mount() {
  const rootEl = document.getElementById('flow-editor-root');
  const hiddenInput = document.getElementById('nodes_json');
  if (!rootEl || !hiddenInput) return;

  let initialNodes = [];
  try {
    const raw = rootEl.dataset.nodes || '[]';
    initialNodes = JSON.parse(raw);
  } catch {
    initialNodes = [];
  }

  let latest = initialNodes;
  const editorRef = createRef();

  const syncHidden = (nodes) => {
    latest = nodes;
    const json = JSON.stringify(nodes, null, 2);
    hiddenInput.value = json;
    const pre = document.getElementById('nodes_json_preview');
    if (pre) pre.textContent = json;
  };

  const onChange = (nodes) => syncHidden(nodes);

  hiddenInput.value = JSON.stringify(initialNodes, null, 2);

  const form = rootEl.closest('form');
  if (form) {
    form.addEventListener('submit', () => {
      const fresh = editorRef.current?.getNodes?.();
      if (fresh) syncHidden(fresh);
      hiddenInput.value = JSON.stringify(latest, null, 2);
    }, true);
  }

  createRoot(rootEl).render(
    <FlowEditor editorRef={editorRef} initialNodes={initialNodes} onChange={onChange} />
  );
}

mount();
