import cytoscape from "cytoscape";
import fcose from "cytoscape-fcose";
import { useEffect, useMemo, useRef, useState } from "react";
import type { GraphData, GraphNode } from "../api";
import { ATTRIBUTE_SHORT, attributeLabel, LEVEL_LABELS, score } from "../format";
import { cssVar } from "../hooks";

cytoscape.use(fcose);

const MAX_FIT_ZOOM = 1.6;
const MAX_LABELLED_EDGES = 12;
// Graphs made of more separate groups than this use the packed-rings layout.
const PACK_COMPONENTS_OVER = 5;

/**
 * Lay out many disconnected groups: each group becomes a circle of its
 * members (highest risk first) and the circles are packed row by row in
 * the order the server sent them (highest ring score first). Force-directed
 * layouts are slow and tangled for hundreds of small separate rings.
 */
function packedRingsLayout(cy: cytoscape.Core, order: Map<string, number>, risk: Map<string, number>): void {
  const groups = cy
    .elements()
    .components()
    .map((component) => {
      const nodes = component.nodes().toArray();
      nodes.sort((a, b) => (risk.get(b.id()) ?? 0) - (risk.get(a.id()) ?? 0));
      const radius = nodes.length <= 1 ? 0 : Math.max(22, (nodes.length * 30) / (2 * Math.PI));
      const rank = Math.min(...nodes.map((node) => order.get(node.id()) ?? Number.MAX_SAFE_INTEGER));
      return { nodes, radius, rank };
    })
    .sort((a, b) => a.rank - b.rank);
  const gap = 36;
  const area = groups.reduce((sum, group) => sum + (2 * group.radius + gap) ** 2, 0);
  const rowWidth = Math.max(500, Math.sqrt(area) * 1.15);
  let x = 0;
  let y = 0;
  let rowHeight = 0;
  cy.batch(() => {
    for (const group of groups) {
      const size = 2 * group.radius + gap;
      if (x > 0 && x + size > rowWidth) {
        x = 0;
        y += rowHeight;
        rowHeight = 0;
      }
      const centerX = x + size / 2;
      const centerY = y + size / 2;
      group.nodes.forEach((node, index) => {
        const angle = (2 * Math.PI * index) / group.nodes.length - Math.PI / 2;
        node.position({
          x: centerX + group.radius * Math.cos(angle),
          y: centerY + group.radius * Math.sin(angle),
        });
      });
      x += size;
      rowHeight = Math.max(rowHeight, size);
    }
  });
}

export type ColorMode = "risk" | "truth";

interface Props {
  data: GraphData;
  size?: "compact" | "default" | "tall";
  center?: string | null;
  selected?: string | null;
  onSelect?: (node: GraphNode | null) => void;
  onOpen?: (node: GraphNode) => void;
  colorMode?: ColorMode;
  dimmed?: Set<string>;
  theme: string;
  emptyText?: string;
}

interface Hover {
  x: number;
  y: number;
  lines: { strong: string; rest: string[] };
}

function colors() {
  return {
    high: cssVar("--risk-high"),
    medium: cssVar("--risk-medium"),
    low: cssVar("--risk-low"),
    surface: cssVar("--surface"),
    text: cssVar("--text"),
    text2: cssVar("--text-2"),
    edge: cssVar("--axis"),
    edgeHover: cssVar("--accent"),
    ring: cssVar("--node-ring"),
    accent: cssVar("--accent"),
  };
}

function nodeColor(node: GraphNode, mode: ColorMode, palette: ReturnType<typeof colors>): string {
  if (mode === "truth") {
    if (node.label === 1) return palette.high;
    if (node.label === 0) return palette.low;
    return palette.surface;
  }
  return palette[node.level];
}

/** Fit everything, but never blow a small ring up to a giant zoom level. */
function fitView(cy: cytoscape.Core): void {
  cy.fit(undefined, 30);
  if (cy.zoom() > MAX_FIT_ZOOM) {
    cy.zoom(MAX_FIT_ZOOM);
    cy.center();
  }
}

function nodeShape(node: GraphNode): string {
  if (node.analyst_label === 1) return "diamond";
  if (node.analyst_label === 0) return "round-rectangle";
  return "ellipse";
}

export default function GraphView({
  data,
  size = "default",
  center,
  selected,
  onSelect,
  onOpen,
  colorMode = "risk",
  dimmed,
  theme,
  emptyText = "Nothing to show",
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const boxRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<cytoscape.Core | null>(null);
  const [hover, setHover] = useState<Hover | null>(null);
  const [laidOut, setLaidOut] = useState(false);
  const small = data.nodes.length <= 60;
  const edgeLabels = small && data.edges.length <= MAX_LABELLED_EDGES;
  const onSelectRef = useRef(onSelect);
  onSelectRef.current = onSelect;
  const onOpenRef = useRef(onOpen);
  onOpenRef.current = onOpen;

  const nodeById = useMemo(() => new Map(data.nodes.map((node) => [node.id, node])), [data]);

  // Build the graph whenever the data changes.
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    setLaidOut(false);
    const elements: cytoscape.ElementDefinition[] = [
      ...data.nodes.map((node) => ({
        group: "nodes" as const,
        data: {
          id: node.id,
          short: node.name.length > 18 ? `${node.name.slice(0, 17)}…` : node.name,
        },
      })),
      ...data.edges.map((edge, index) => ({
        group: "edges" as const,
        data: {
          id: `e${index}`,
          source: edge.source,
          target: edge.target,
          weight: edge.weight,
          label: edge.types.map((kind) => ATTRIBUTE_SHORT[kind] ?? kind).join(" · "),
          types: edge.types,
        },
      })),
    ];
    const cy = cytoscape({
      container,
      elements,
      minZoom: 0.05,
      maxZoom: 4,
      boxSelectionEnabled: false,
    });
    cyRef.current = cy;

    cy.on("tap", "node", (event) => {
      const node = nodeById.get(event.target.id());
      onSelectRef.current?.(node ?? null);
    });
    cy.on("dbltap", "node", (event) => {
      const node = nodeById.get(event.target.id());
      if (node) onOpenRef.current?.(node);
    });
    cy.on("tap", (event) => {
      if (event.target === cy) onSelectRef.current?.(null);
    });
    cy.on("mouseover", "node", (event) => {
      const node = nodeById.get(event.target.id());
      if (!node) return;
      const position = event.renderedPosition;
      const rest = [`${LEVEL_LABELS[node.level]} risk · ring ${node.ring_id ?? "none"}`, `${node.degree} linked accounts`];
      if (node.analyst_label !== null && node.analyst_label !== undefined) {
        rest.push(node.analyst_label === 1 ? "Analyst: fraud" : "Analyst: legitimate");
      }
      if (node.label !== null && node.label !== undefined) rest.push(`Known label: ${node.label === 1 ? "fraud" : "legitimate"}`);
      setHover({ x: position.x, y: position.y, lines: { strong: `${score(node.risk)} · ${node.name}`, rest } });
      container.style.cursor = "pointer";
    });
    cy.on("mouseout", "node, edge", (event) => {
      event.target.removeClass("hovered");
      setHover(null);
      container.style.cursor = "";
    });
    cy.on("mouseover", "edge", (event) => {
      const edge = event.target;
      edge.addClass("hovered");
      const position = event.renderedPosition;
      const types = (edge.data("types") as string[]).map(attributeLabel).join(", ");
      setHover({ x: position.x, y: position.y, lines: { strong: `Shared ${types}`, rest: [] } });
    });

    if (cy.elements().components().length > PACK_COMPONENTS_OVER) {
      packedRingsLayout(
        cy,
        new Map(data.nodes.map((node, index) => [node.id, index])),
        new Map(data.nodes.map((node) => [node.id, node.risk])),
      );
      fitView(cy);
      setLaidOut(true);
    } else {
      const layout = cy.layout({
        name: "fcose",
        quality: "default",
        randomize: true,
        animate: false,
        nodeRepulsion: () => 5500,
        idealEdgeLength: () => (small ? 70 : 50),
        nodeSeparation: 60,
        padding: 30,
      } as cytoscape.LayoutOptions);
      layout.one("layoutstop", () => {
        fitView(cy);
        setLaidOut(true);
      });
      layout.run();
    }

    return () => {
      cy.destroy();
      cyRef.current = null;
    };
  }, [data, nodeById, small]);

  // Styling depends on theme, colour mode, selection and dimming.
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    const palette = colors();
    cy.style([
      {
        selector: "node",
        style: {
          "background-color": (element: cytoscape.NodeSingular) => {
            const node = nodeById.get(element.id());
            return node ? nodeColor(node, colorMode, palette) : palette.low;
          },
          shape: ((element: cytoscape.NodeSingular) => {
            const node = nodeById.get(element.id());
            return node ? nodeShape(node) : "ellipse";
          }) as unknown as cytoscape.Css.NodeShape,
          width: (element: cytoscape.NodeSingular) => {
            const node = nodeById.get(element.id());
            if (!node) return 14;
            const base = node.level === "high" ? 24 : node.level === "medium" ? 19 : 14;
            return element.id() === center ? base + 10 : base;
          },
          height: (element: cytoscape.NodeSingular) => {
            const node = nodeById.get(element.id());
            if (!node) return 14;
            const base = node.level === "high" ? 24 : node.level === "medium" ? 19 : 14;
            return element.id() === center ? base + 10 : base;
          },
          "border-width": (element: cytoscape.NodeSingular) => {
            const node = nodeById.get(element.id());
            return colorMode === "truth" && node && node.label === null ? 1.5 : 2;
          },
          "border-color": (element: cytoscape.NodeSingular) => {
            const node = nodeById.get(element.id());
            return colorMode === "truth" && node && node.label === null ? palette.text2 : palette.surface;
          },
          opacity: (element: cytoscape.NodeSingular) => (dimmed?.has(element.id()) ? 0.35 : 1),
          label: small ? "data(short)" : "",
          "font-size": 9,
          color: palette.text2,
          "text-valign": "bottom",
          "text-margin-y": 3,
          "text-outline-color": palette.surface,
          "text-outline-width": 2,
        },
      },
      {
        selector: "edge",
        style: {
          width: (element: cytoscape.EdgeSingular) => 0.8 + Number(element.data("weight")) * 0.9,
          "line-color": palette.edge,
          "curve-style": small ? "bezier" : "haystack",
          opacity: (element: cytoscape.EdgeSingular) =>
            dimmed && (dimmed.has(element.source().id()) || dimmed.has(element.target().id())) ? 0.3 : 0.9,
          label: edgeLabels ? "data(label)" : "",
          "font-size": 8,
          color: palette.text2,
          "text-rotation": "autorotate",
          "text-background-color": palette.surface,
          "text-background-opacity": 0.85,
          "text-background-padding": "1px",
        },
      },
      {
        selector: "edge:active, edge.hovered",
        style: { "line-color": palette.edgeHover },
      },
      {
        selector: `node[id = "${(selected ?? "").replace(/"/g, '\\"')}"]`,
        style: { "border-width": 3.5, "border-color": palette.ring },
      },
      {
        selector: `node[id = "${(center ?? "").replace(/"/g, '\\"')}"]`,
        style: { "border-width": 3.5, "border-color": palette.accent },
      },
    ] as cytoscape.StylesheetJson);
  }, [theme, colorMode, selected, center, dimmed, nodeById, small, edgeLabels, laidOut]);

  // Centre on an externally selected node (for example from a search box).
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy || !selected || !laidOut) return;
    const element = cy.getElementById(selected);
    if (element.nonempty()) cy.animate({ center: { eles: element }, zoom: Math.max(cy.zoom(), 1.2) }, { duration: 300 });
  }, [selected, laidOut]);

  const fit = () => {
    if (cyRef.current) fitView(cyRef.current);
  };
  const zoom = (factor: number) => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.zoom({ level: cy.zoom() * factor, renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 } });
  };

  return (
    <div className={`graph-box ${size === "default" ? "" : size}`} ref={boxRef}>
      <div className="graph-canvas" ref={containerRef} aria-label="Customer identity network" role="img" />
      {data.nodes.length === 0 && <div className="graph-overlay">{emptyText}</div>}
      {data.nodes.length > 0 && !laidOut && (
        <div className="graph-overlay">
          <span className="spinner" />
          &nbsp;Laying out {data.nodes.length.toLocaleString()} accounts…
        </div>
      )}
      <div className="graph-controls">
        <button className="btn small" onClick={() => zoom(1.25)} aria-label="Zoom in">
          +
        </button>
        <button className="btn small" onClick={() => zoom(0.8)} aria-label="Zoom out">
          −
        </button>
        <button className="btn small" onClick={fit}>
          Fit
        </button>
      </div>
      <div className="graph-legend legend">
        {colorMode === "risk" ? (
          <>
            <span>
              <span className="ring-swatch" style={{ background: "var(--risk-high)" }} /> High
            </span>
            <span>
              <span className="ring-swatch" style={{ background: "var(--risk-medium)", width: 9, height: 9 }} /> Medium
            </span>
            <span>
              <span className="ring-swatch" style={{ background: "var(--risk-low)", width: 7, height: 7 }} /> Low
            </span>
          </>
        ) : (
          <>
            <span>
              <span className="ring-swatch" style={{ background: "var(--risk-high)" }} /> Known fraud
            </span>
            <span>
              <span className="ring-swatch" style={{ background: "var(--risk-low)" }} /> Known legit
            </span>
          </>
        )}
        <span>◆ analyst fraud</span>
        <span>▢ analyst legit</span>
        <span>line width = shared identifiers</span>
      </div>
      {hover && (
        <div
          className="tooltip"
          style={{
            left: Math.min(hover.x + 14, (boxRef.current?.clientWidth ?? 600) - 290),
            top: hover.y + 14,
          }}
        >
          <div className="tt-value">{hover.lines.strong}</div>
          {hover.lines.rest.map((line) => (
            <div className="tt-row" key={line}>
              {line}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
