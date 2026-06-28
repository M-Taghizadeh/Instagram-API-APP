import { createRef } from 'react';
import { createRoot } from 'react-dom/client';
import FlowEditor from './FlowEditor';
import './editor.css';

function readInitialNodes(hiddenInput) {
  const dataEl = document.getElementById('flow-editor-nodes-data');
  if (dataEl?.textContent?.trim()) {
    try {
      const parsed = JSON.parse(dataEl.textContent);
      if (Array.isArray(parsed)) return parsed;
    } catch {
      /* fall through */
    }
  }

  const raw = hiddenInput?.value?.trim();
  if (raw) {
    try {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed)) return parsed;
    } catch {
      /* fall through */
    }
  }

  return [];
}

function mount() {
  const rootEl = document.getElementById('flow-editor-root');
  const hiddenInput = document.getElementById('nodes_json');
  if (!rootEl || !hiddenInput) return;

  const initialNodes = readInitialNodes(hiddenInput);
  let latest = initialNodes;
  const editorRef = createRef();

  const syncHidden = (nodes) => {
    latest = nodes;
    const json = JSON.stringify(nodes);
    hiddenInput.value = json;
    const pre = document.getElementById('nodes_json_preview');
    if (pre) pre.textContent = JSON.stringify(nodes, null, 2);
  };

  const onChange = (nodes) => syncHidden(nodes);

  if (initialNodes.length) {
    syncHidden(initialNodes);
  }

  const form = rootEl.closest('form');
  if (form) {
    form.addEventListener(
      'submit',
      (e) => {
        const fresh = editorRef.current?.getNodes?.();
        if (fresh) syncHidden(fresh);
        if (!latest.length) {
          e.preventDefault();
          window.alert('حداقل یک نود در ویرایشگر بسازید و به هم وصل کنید.');
          return;
        }
        hiddenInput.value = JSON.stringify(latest);
      },
      true,
    );
  }

  createRoot(rootEl).render(
    <FlowEditor ref={editorRef} initialNodes={initialNodes} onChange={onChange} />,
  );
}

mount();
