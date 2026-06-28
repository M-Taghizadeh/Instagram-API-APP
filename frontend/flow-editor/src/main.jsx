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
  const onChange = (nodes) => {
    latest = nodes;
    const json = JSON.stringify(nodes, null, 2);
    hiddenInput.value = json;
    const pre = document.getElementById('nodes_json_preview');
    if (pre) pre.textContent = json;
  };

  hiddenInput.value = JSON.stringify(initialNodes, null, 2);

  const form = rootEl.closest('form');
  if (form) {
    form.addEventListener('submit', () => {
      hiddenInput.value = JSON.stringify(latest, null, 2);
    });
  }

  createRoot(rootEl).render(
    <FlowEditor initialNodes={initialNodes} onChange={onChange} />
  );
}

mount();
