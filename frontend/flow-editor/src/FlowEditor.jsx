import { useCallback, useEffect, useImperativeHandle, useRef, useState, forwardRef } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  addEdge,
  useNodesState,
  useEdgesState,
  ReactFlowProvider,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import FlowNode from './FlowNode';
import NodePanel from './NodePanel';
import useTheme from './useTheme';
import { NODE_TYPES } from './nodeMeta';
import { defaultDataForType, fromReactFlow, newNodeId, toReactFlow } from './serialize';

const nodeTypes = { flowNode: FlowNode };

const FlowEditorInner = forwardRef(function FlowEditorInner({ initialNodes, onChange }, ref) {
  const initial = useRef(toReactFlow(initialNodes)).current;
  const [nodes, setNodes, onNodesChange] = useNodesState(initial.nodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initial.edges);
  const [selectedId, setSelectedId] = useState(null);
  const nodesRef = useRef(nodes);
  const edgesRef = useRef(edges);

  nodesRef.current = nodes;
  edgesRef.current = edges;

  const serialize = useCallback(() => {
    return fromReactFlow(nodesRef.current, edgesRef.current);
  }, []);

  const emit = useCallback(() => {
    onChange?.(serialize());
  }, [onChange, serialize]);

  useImperativeHandle(ref, () => ({
    getNodes: serialize,
  }), [serialize]);

  useEffect(() => {
    emit();
  }, [nodes, edges, emit]);

  const onConnect = useCallback(
    (connection) => {
      setEdges((eds) => addEdge({ ...connection, type: 'smoothstep', animated: true }, eds));
    },
    [setEdges]
  );

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
    setNodes((nds) => [...nds, newNode]);
    setSelectedId(id);
  };

  const updateNodeData = (id, data) => {
    setNodes((nds) => nds.map((n) => (n.id === id ? { ...n, data } : n)));
  };

  const setStartNode = (id, isStart) => {
    setNodes((nds) => nds.map((n) => ({
      ...n,
      data: {
        ...n.data,
        isStart: n.id === id ? isStart : isStart ? false : n.data.isStart,
      },
    })));
  };

  const deleteNode = (id) => {
    setNodes((nds) => nds.filter((n) => n.id !== id));
    setEdges((eds) => eds.filter((e) => e.source !== id && e.target !== id));
    setSelectedId(null);
  };

  const onNodesDelete = useCallback(
    (deleted) => {
      const ids = new Set(deleted.map((n) => n.id));
      setNodes((nds) => nds.filter((n) => !ids.has(n.id)));
      setEdges((eds) => eds.filter((e) => !ids.has(e.source) && !ids.has(e.target)));
    },
    [setNodes, setEdges]
  );

  const selectedNode = nodes.find((n) => n.id === selectedId) || null;
  const theme = useTheme();
  const isLight = theme === 'light';

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
          nodeTypes={nodeTypes}
          fitView
          onNodeClick={(_, node) => setSelectedId(node.id)}
          onPaneClick={() => setSelectedId(null)}
          deleteKeyCode={['Backspace', 'Delete']}
          onNodesDelete={onNodesDelete}
        >
          <Background gap={18} size={1} color={isLight ? '#e4e4e7' : '#2a2548'} />
          <Controls showInteractive={false} />
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
});

export default forwardRef(function FlowEditor(props, ref) {
  return (
    <ReactFlowProvider>
      <FlowEditorInner ref={ref} {...props} />
    </ReactFlowProvider>
  );
});
