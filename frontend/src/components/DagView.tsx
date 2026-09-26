'use client';

import { useCallback, useMemo } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
  type NodeTypes,
  MarkerType,
  Position,
  Handle,
  BackgroundVariant,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import dagre from 'dagre';
import { useAppStore } from '@/stores/taskStore';
import type { GraphNode } from '@/types';

// ─── Custom Node Component ──────────────────────────────────

function TaskNode({ data }: { data: GraphNode & { onNodeClick: (id: string) => void } }) {
  const statusColors: Record<string, string> = {
    backlog: 'var(--status-backlog)',
    in_progress: 'var(--status-in-progress)',
    review: 'var(--status-review)',
    done: 'var(--status-done)',
  };

  const borderColor = data.is_blocked
    ? 'var(--state-blocked)'
    : data.on_critical_path
    ? 'var(--critical-color)'
    : data.status === 'done'
    ? 'var(--status-done)'
    : 'var(--border-medium)';

  const boxShadow = data.on_critical_path
    ? 'var(--critical-glow)'
    : data.is_blocked
    ? '0 0 12px rgba(239, 68, 68, 0.2)'
    : 'none';

  return (
    <div
      className="dag-node"
      style={{ borderColor, boxShadow, cursor: 'pointer' }}
      onClick={() => data.onNodeClick(data.id)}
    >
      <Handle type="target" position={Position.Top} style={{ background: borderColor, width: 8, height: 8 }} />
      <div className="dag-node-title">{data.title}</div>
      <div className="dag-node-status">
        <span
          className="dag-node-status-dot"
          style={{ backgroundColor: statusColors[data.status] || 'var(--text-tertiary)' }}
        />
        {data.status.replace('_', ' ')}
        <span style={{ marginLeft: 'auto', fontFamily: 'var(--font-mono)', fontSize: '0.625rem' }}>
          {data.duration_days}d
        </span>
      </div>
      {data.is_blocked && (
        <div style={{ fontSize: '0.625rem', color: 'var(--state-blocked)', marginTop: 4 }}>
          🔒 Blocked
        </div>
      )}
      <Handle type="source" position={Position.Bottom} style={{ background: borderColor, width: 8, height: 8 }} />
    </div>
  );
}

const nodeTypes: NodeTypes = {
  taskNode: TaskNode,
};

// ─── Dagre Layout ───────────────────────────────────────────

function getLayoutedElements(
  nodes: Node[],
  edges: Edge[],
  direction = 'TB'
) {
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: direction, nodesep: 60, ranksep: 80 });

  nodes.forEach((node) => {
    g.setNode(node.id, { width: 200, height: 80 });
  });

  edges.forEach((edge) => {
    g.setEdge(edge.source, edge.target);
  });

  dagre.layout(g);

  const layoutedNodes = nodes.map((node) => {
    const nodeWithPosition = g.node(node.id);
    return {
      ...node,
      position: {
        x: nodeWithPosition.x - 100,
        y: nodeWithPosition.y - 40,
      },
    };
  });

  return { nodes: layoutedNodes, edges };
}

// ─── DAG View Component ─────────────────────────────────────

export default function DagView() {
  const { graphData, setSelectedTaskId, openSidePanel } = useAppStore();

  const handleNodeClick = useCallback(
    (id: string) => {
      setSelectedTaskId(id);
      openSidePanel('task-detail');
    },
    [setSelectedTaskId, openSidePanel]
  );

  const { initialNodes, initialEdges } = useMemo(() => {
    if (!graphData) return { initialNodes: [], initialEdges: [] };

    const criticalSet = new Set(graphData.critical_path);
    const criticalEdgeSet = new Set<string>();
    for (let i = 0; i < graphData.critical_path.length - 1; i++) {
      criticalEdgeSet.add(`${graphData.critical_path[i]}->${graphData.critical_path[i + 1]}`);
    }

    const rawNodes: Node[] = graphData.nodes.map((node) => ({
      id: node.id,
      type: 'taskNode',
      position: { x: 0, y: 0 },
      data: {
        ...node,
        on_critical_path: criticalSet.has(node.id),
        onNodeClick: handleNodeClick,
      },
    }));

    const rawEdges: Edge[] = graphData.edges.map((edge) => {
      const isCritical = criticalEdgeSet.has(`${edge.source}->${edge.target}`);
      return {
        id: edge.id,
        source: edge.source,
        target: edge.target,
        type: 'default',
        animated: isCritical,
        style: {
          stroke: isCritical ? 'var(--critical-color)' : 'var(--text-tertiary)',
          strokeWidth: isCritical ? 3 : 1.5,
        },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: isCritical ? 'var(--critical-color)' : 'var(--text-tertiary)',
          width: 16,
          height: 16,
        },
        className: isCritical ? 'critical' : '',
      };
    });

    const { nodes: layoutedNodes, edges: layoutedEdges } = getLayoutedElements(
      rawNodes,
      rawEdges
    );

    return { initialNodes: layoutedNodes, initialEdges: layoutedEdges };
  }, [graphData, handleNodeClick]);

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  // Update nodes/edges when graph data changes
  useMemo(() => {
    setNodes(initialNodes);
    setEdges(initialEdges);
  }, [initialNodes, initialEdges, setNodes, setEdges]);

  if (!graphData || graphData.nodes.length === 0) {
    return (
      <div className="dag-container">
        <div className="empty-state">
          <div className="empty-state-icon">◈</div>
          <div className="empty-state-title">No Tasks Yet</div>
          <div className="empty-state-text">
            Create tasks and add dependencies to see the dependency graph.
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="dag-container">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        minZoom={0.3}
        maxZoom={2}
        proOptions={{ hideAttribution: true }}
      >
        <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="rgba(255,255,255,0.05)" />
        <Controls
          style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--border-subtle)' }}
        />
        <MiniMap
          nodeColor={(node) => {
            const data = node.data as GraphNode;
            if (data?.is_blocked) return 'var(--state-blocked)';
            if (data?.status === 'done') return 'var(--status-done)';
            return 'var(--accent-primary)';
          }}
          maskColor="rgba(0, 0, 0, 0.6)"
          style={{ background: 'var(--bg-tertiary)' }}
        />
      </ReactFlow>
    </div>
  );
}
