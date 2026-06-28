import { useCallback, useMemo, useState } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  addEdge,
  useNodesState,
  useEdgesState,
  ReactFlowProvider,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import FlowNode from './FlowNode';
import NodePanel from './NodePanel';
import { NODE_TYPES } from './nodeMeta';
import { defaultDataForType, fromReactFlow, newNodeId, toReactFlow } from './serialize';

const nodeTypes = { flowNode: FlowNode };

function FlowEditorInner({ initialNodes, onChange }) {
  const initial = useMemo(() => toReactFlow(initialNodes), [initialNodes]);
  const [nodes, setNodes, onNodesChange] = useNodesState(initial.nodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initial.edges);
  const [selectedId, setSelectedId] = useState(null);

  const selectedNode = nodes.find((n) => n.id === selectedId) || null;

  const emit = useCallback(
    (nextNodes, nextEdges) => {
      onChange?.(fromReactFlow(nextNodes, nextEdges));
    },
    [onChange]
  );

  const onConnect = useCallback(
    (connection) => {
      setEdges((eds) => {
        const next = addEdge({ ...connection, type: 'smoothstep', animated: true }, eds);
        emit(nodes, next);
        return next;
      });
    },
    [nodes, emit, setEdges]
  );

  const onNodeDragStop = useCallback(() => {
    emit(nodes, edges);
  }, [nodes, edges, emit]);

  const addNode = (type) => {
    const id = newNodeId();
    const y = nodes.length * 130 + 40;
    const newNode = {
      id,
      type: 'flowNode',
      position: { x: 280, y },
      data: {
        nodeType: type,
        isStart: nodes.length === 0,
        ...defaultDataForType(type),
      },
    };
    const nextNodes = [...nodes, newNode];
    setNodes(nextNodes);
    setSelectedId(id);
    emit(nextNodes, edges);
  };

  const updateNodeData = (id, data) => {
    const nextNodes = nodes.map((n) => (n.id === id ? { ...n, data } : n));
    setNodes(nextNodes);
    emit(nextNodes, edges);
  };

  const setStartNode = (id, isStart) => {
    const nextNodes = nodes.map((n) => ({
      ...n,
      data: {
        ...n.data,
        isStart: n.id === id ? isStart : isStart ? false : n.data.isStart,
      },
    }));
    setNodes(nextNodes);
    emit(nextNodes, edges);
  };

  const deleteNode = (id) => {
    const nextNodes = nodes.filter((n) => n.id !== id);
    const nextEdges = edges.filter((e) => e.source !== id && e.target !== id);
    setNodes(nextNodes);
    setEdges(nextEdges);
    setSelectedId(null);
    emit(nextNodes, nextEdges);
  };

  const onNodesDelete = useCallback(
    (deleted) => {
      const ids = new Set(deleted.map((n) => n.id));
      const nextNodes = nodes.filter((n) => !ids.has(n.id));
      const nextEdges = edges.filter((e) => !ids.has(e.source) && !ids.has(e.target));
      setNodes(nextNodes);
      setEdges(nextEdges);
      emit(nextNodes, nextEdges);
    },
    [nodes, edges, setNodes, setEdges, emit]
  );

  return (
    <div className="fe-layout">
      <aside className="fe-palette">
        <div className="fe-palette-title">افزودن نود</div>
        {NODE_TYPES.map((item) => (
          <button
            key={item.type}
            type="button"
            className="fe-palette-btn"
            onClick={() => addNode(item.type)}
          >
            <span>{item.icon}</span> {item.label}
          </button>
        ))}
      </aside>

      <div className="fe-canvas-wrap">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          onNodeDragStop={onNodeDragStop}
          nodeTypes={nodeTypes}
          fitView
          onNodeClick={(_, node) => setSelectedId(node.id)}
          onPaneClick={() => setSelectedId(null)}
          deleteKeyCode={['Backspace', 'Delete']}
          onNodesDelete={onNodesDelete}
        >
          <Background gap={18} size={1} color="#2a2548" />
          <Controls showInteractive={false} />
          <MiniMap
            nodeColor={() => '#6c4fff'}
            maskColor="rgba(7,6,14,.75)"
            style={{ background: '#110f1e' }}
          />
        </ReactFlow>
      </div>

      <NodePanel
        node={selectedNode}
        onChange={updateNodeData}
        onDelete={deleteNode}
        onSetStart={setStartNode}
      />
    </div>
  );
}

export default function FlowEditor(props) {
  return (
    <ReactFlowProvider>
      <FlowEditorInner {...props} />
    </ReactFlowProvider>
  );
}
