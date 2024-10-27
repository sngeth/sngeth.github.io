---
layout: post
title: "Making a D3 Sankey Chart Responsive in React"
category: "Javascript"
comments: true
---

Creating data visualizations that work well across different screen sizes can be challenging. Today, I'll walk you through how I enhanced a D3.js Sankey chart to be more responsive in a React application. Here's how we made our chart adapt seamlessly to any screen size.
The app is deployed [here](http://cashflow.sngeth.com) and the full source code is [http://github.com/sngeth/cash-flow](http://github.com/sngeth/cash-flow)

## The Challenge

Our initial Sankey chart worked well on desktop but had several limitations on smaller screens:
- Labels would overlap on narrow viewports
- Node spacing was too wide for mobile screens
- Font sizes were too large for smaller displays
- The chart wouldn't resize smoothly on window resize

## Key Responsive Improvements

### 1. Dynamic SVG Dimensions

```jsx
export default function SankeyChart({ income, savings, billItems }: SankeyChartProps) {
  const svgRef = useRef<SVGSVGElement>(null);

  const createChart = useCallback(() => {
    if (!svgRef.current) return;

    const svg = d3.select(svgRef.current);
    const width = svg.node()!.getBoundingClientRect().width;
    const height = svg.node()!.getBoundingClientRect().height;
  ...
}
```


### 2. Adaptive Node Padding

We adjust the spacing between nodes based on screen width:

```javascript
const nodePadding = width < 600 ? 10 : 20;

const sankeyGenerator = sankey<SankeyNodeExtended, SankeyLink<SankeyNodeExtended, {}>>()
  .nodeWidth(10)
  .nodePadding(nodePadding)
  .extent([[1, 1], [width - 1, height - 6]]);
```

This provides:
- Comfortable spacing on desktop (20px)
- Compact layout on mobile (10px)
- Better use of available space across all devices

### 3. Responsive Text Handling

We implement dynamic font sizing based on viewport width:

```javascript
const fontSize = width < 600 ? "10px" : "12px";

node.append("text")
  .attr("font-size", fontSize)
  .attr("x", d => (d.x0 ?? 0) < width / 2 ? (d.x1 ?? 0) + 6 : (d.x0 ?? 0) - 6)
  .attr("y", d => ((d.y1 ?? 0) + (d.y0 ?? 0)) / 2)
  .attr("dy", "0.35em")
  .attr("text-anchor", d => (d.x0 ?? 0) < width / 2 ? "start" : "end")
  .text(d => `${d.name}: $${d.value ?? 0}`);
```

Key features:
- Smaller font on mobile devices
- Dynamic text positioning
- Smart text anchor points based on node position

### 4. Smooth Resize Handling

We implemented efficient window resize handling:

```javascript
useEffect(() => {
  createChart();
  const handleResize = () => {
    createChart();
  };
  window.addEventListener('resize', handleResize);
  return () => {
    window.removeEventListener('resize', handleResize);
  };
}, [createChart]);
```

This ensures:
- Chart redraws on window resize
- Clean cleanup of event listeners
- Smooth transitions between sizes

### 5. Clean Redraws

Before each redraw, we clear the previous chart:

```javascript
svg.selectAll('*').remove();
```
