import { forwardRef, useEffect, useImperativeHandle, useRef } from 'react'
import { COLORS } from '../collection/analysis'

const PALETTE = ['#ff775f','#66e3b4','#d9ff43','#46d8df','#a78bfa','#fb7185','#60a5fa','#fbbf24','#34d399','#f472b6']
const color = n => PALETTE[n % PALETTE.length]
const esc = value => String(value).replace(/[<>&"']/g, c => ({'<':'&lt;','>':'&gt;','&':'&amp;','"':'&quot;',"'":'&apos;'}[c]))

function communities(nodes, edges) {
    const index = new Map(nodes.map((n, i) => [n.id, i])), labels = nodes.map((_, i) => i), neighbors = nodes.map(() => [])
    edges.forEach(e => { const a = index.get(e.source), b = index.get(e.target); if (a != null && b != null) { neighbors[a].push(b); neighbors[b].push(a) } })
    for (let pass = 0; pass < 7; pass++) for (let i = 0; i < nodes.length; i++) {
        const counts = new Map(); neighbors[i].forEach(j => counts.set(labels[j], (counts.get(labels[j]) || 0) + 1))
        let best = labels[i], count = 0; counts.forEach((n, label) => { if (n > count || (n === count && label < best)) { best = label; count = n } }); labels[i] = best
    }
    const sizes = new Map(); labels.forEach(v => sizes.set(v, (sizes.get(v) || 0) + 1))
    const normalized = new Map([...sizes].sort((a,b) => b[1] - a[1]).map(([v], i) => [v, i]))
    return labels.map(v => normalized.get(v))
}

class Renderer {
    constructor(canvas, onPick) {
        this.canvas = canvas; this.ctx = canvas.getContext('2d'); this.onPick = onPick
        this.scale = 1; this.x = 0; this.y = 0; this.drag = null; this.hover = null; this.separated = false
        // ResizeObserver can request a draw before React's graph effect runs.
        // Keep the renderer valid during that initial empty frame.
        this.nodes = []; this.edges = []; this.options = { colors: true, widthMode: 'consensus', labels: true, nodeScale: 1 }
        this.bind(); this.resize()
    }
    setGraph(graph, options) {
        cancelAnimationFrame(this.frame); this.options = options
        const old = new Map((this.nodes || []).map(n => [n.id, n]))
        this.nodes = graph.nodes.map(n => ({ ...n, x: old.get(n.id)?.x || 0, y: old.get(n.id)?.y || 0, vx: 0, vy: 0, degree: 0 }))
        const byId = new Map(this.nodes.map(n => [n.id, n])); this.edges = graph.edges.map(e => ({ ...e, a: byId.get(e.source), b: byId.get(e.target) })).filter(e => e.a && e.b)
        this.edges.forEach(e => { e.a.degree++; e.b.degree++ }); const groups = communities(this.nodes, this.edges); this.nodes.forEach((n,i) => n.community = groups[i])
        if (!old.size) this.seed(); this.tick = 0; this.animate(); this.fit()
    }
    seed() {
        const placed = new Map(), count = Math.max(1, new Set(this.nodes.map(n => n.community)).size)
        this.nodes.forEach(n => { const i = placed.get(n.community) || 0; placed.set(n.community, i + 1); const a = n.community / count * Math.PI * 2 + i * 2.399, r = 55 + Math.sqrt(i) * 16; n.x = this.width/2 + Math.cos(a)*r; n.y = this.height/2 + Math.sin(a)*r })
    }
    animate(limit=260) { const step=()=>{ for(let i=0;i<2;i++) this.simulate(); this.draw(); if(this.tick++<limit) this.frame=requestAnimationFrame(step) }; step() }
    simulate() {
        const grid=new Map(), cell=45; this.nodes.forEach(n=>{const k=`${Math.floor(n.x/cell)},${Math.floor(n.y/cell)}`;(grid.get(k)||grid.set(k,[]).get(k)).push(n)})
        this.nodes.forEach(n=>{const gx=Math.floor(n.x/cell),gy=Math.floor(n.y/cell);for(let ox=-1;ox<=1;ox++)for(let oy=-1;oy<=1;oy++)for(const o of grid.get(`${gx+ox},${gy+oy}`)||[]){if(o===n)continue;let dx=n.x-o.x,dy=n.y-o.y,d=dx*dx+dy*dy||.1;if(d<2200){n.vx+=dx*.8/d;n.vy+=dy*.8/d}}})
        this.edges.forEach(e=>{const dx=e.b.x-e.a.x,dy=e.b.y-e.a.y,d=Math.hypot(dx,dy)||1,ideal=58,separation=(this.separated&&e.a.community!==e.b.community)?.08:1,force=(d-ideal)*.004*separation;e.a.vx+=dx/d*force;e.a.vy+=dy/d*force;e.b.vx-=dx/d*force;e.b.vy-=dy/d*force})
        const cx=this.width/2,cy=this.height/2;this.nodes.forEach(n=>{if(this.drag?.node===n)return;const target=this.targets?.get(n.community);n.vx+=((target?.x??cx)-n.x)*(target?.0018:.0003);n.vy+=((target?.y??cy)-n.y)*(target?.0018:.0003);n.vx*=.84;n.vy*=.84;n.x+=n.vx;n.y+=n.vy})
    }
    edgeColor(e) { const databases=e.databases||[];return !this.options.colors||e.expanded?'#8aa097':databases.length>1?'#d9ff43':COLORS[databases[0]]||'#a6bab1' }
    edgeWidth(e) { if(this.options.widthMode==='off')return 1; if(this.options.widthMode==='score'){const s=(e.evidence||[]).filter(v=>v.score!=null).map(v=>v.score);return 1+(s.length?s.reduce((a,b)=>a+b,0)/s.length:0)*3} return 1+(e.databases||[]).length*1.25 }
    radius(n){return (Math.min(10,3+Math.sqrt(n.degree)*1.1)+(n.input?2:0))*(this.options.nodeScale||1)}
    draw() { const c=this.ctx;if(!c||!this.width)return;c.setTransform(this.dpr,0,0,this.dpr,0,0);const g=c.createRadialGradient(this.width*.45,this.height*.42,0,this.width*.5,this.height*.5,Math.max(this.width,this.height)*.75);g.addColorStop(0,'#19382e');g.addColorStop(.55,'#10231d');g.addColorStop(1,'#0b1b16');c.fillStyle=this.options.backgroundColor||g;c.fillRect(0,0,this.width,this.height);c.fillStyle='#ffffff0a';for(let x=24;x<this.width;x+=44)for(let y=24;y<this.height;y+=44){c.beginPath();c.arc(x,y,.7,0,7);c.fill()}c.save();c.translate(this.x,this.y);c.scale(this.scale,this.scale);(this.edges||[]).forEach(e=>{c.beginPath();c.moveTo(e.a.x,e.a.y);c.lineTo(e.b.x,e.b.y);c.strokeStyle=e===this.selectedEdge?'#fff':this.edgeColor(e);c.globalAlpha=e===this.selectedEdge?1:.2+Math.min(.6,(e.databases||[]).length*.18);c.lineWidth=this.edgeWidth(e)+(e===this.selectedEdge?2/this.scale:0);c.stroke()});c.globalAlpha=1;(this.nodes||[]).forEach(n=>{const r=this.radius(n),fill=n.unresolved?'#d9ff43':n.input?'#ff775f':color(n.community);if(n===this.hover||n===this.selected){c.beginPath();c.arc(n.x,n.y,r+7/this.scale,0,7);c.strokeStyle='#fff';c.lineWidth=1.5/this.scale;c.stroke()}c.beginPath();c.arc(n.x,n.y,r,0,7);c.fillStyle=fill;c.fill();if(n.degree>5){c.strokeStyle='#ffffff99';c.lineWidth=.8;c.stroke()}if(this.options.labels||n===this.hover||n===this.selected){c.font=`${Math.max(8,10/this.scale)}px monospace`;c.fillStyle=this.options.labelColor||'#ffffffe6';c.fillText(n.gene,n.x+r+6/this.scale,n.y+3/this.scale)}});c.restore() }
    fit(nodes=this.nodes){if(!nodes.length)return;let xs=nodes.map(n=>n.x),ys=nodes.map(n=>n.y),minX=Math.min(...xs),maxX=Math.max(...xs),minY=Math.min(...ys),maxY=Math.max(...ys);this.scale=Math.max(.25,Math.min(3,Math.min((this.width-120)/Math.max(80,maxX-minX),(this.height-120)/Math.max(80,maxY-minY))));this.x=this.width/2-(minX+maxX)/2*this.scale;this.y=this.height/2-(minY+maxY)/2*this.scale;this.draw()}
    focus(query){const q=query.trim().toLowerCase(),found=this.nodes.filter(n=>n.id.toLowerCase()===q||n.gene.toLowerCase()===q);if(found.length){this.selected=found[0];this.onPick({kind:'node',data:found[0]});this.fit(found);return true}return false}
    separate(){this.separated=!this.separated;this.targets=new Map();if(this.separated){const groups=new Map();this.nodes.forEach(n=>(groups.get(n.community)||groups.set(n.community,[]).get(n.community)).push(n));const entries=[...groups],cols=Math.ceil(Math.sqrt(entries.length));entries.forEach(([id],i)=>this.targets.set(id,{x:this.width/2+(i%cols-(cols-1)/2)*300,y:this.height/2+(Math.floor(i/cols)-(Math.ceil(entries.length/cols)-1)/2)*250}))}else this.seed();this.tick=0;this.animate(180);return this.separated}
    rearrange(){this.seed();this.tick=0;this.animate();this.fit()}
    resize(){const r=this.canvas.parentElement.getBoundingClientRect(),changed=this.width!==r.width||this.height!==r.height;this.width=Math.max(1,r.width);this.height=Math.max(1,r.height);this.dpr=Math.min(devicePixelRatio||1,2);this.canvas.width=this.width*this.dpr;this.canvas.height=this.height*this.dpr;if(changed&&this.nodes?.length)this.fit();else this.draw()}
    point(e){const r=this.canvas.getBoundingClientRect(),sx=e.clientX-r.left,sy=e.clientY-r.top;return{sx,sy,x:(sx-this.x)/this.scale,y:(sy-this.y)/this.scale}}
    find(p){let hit=null,best=(13/this.scale)**2;this.nodes.forEach(n=>{const d=(n.x-p.x)**2+(n.y-p.y)**2;if(d<best){best=d;hit=n}});return hit}
    findEdge(p){let hit=null,best=(4/this.scale)**2;this.edges.forEach(e=>{const dx=e.b.x-e.a.x,dy=e.b.y-e.a.y,l=dx*dx+dy*dy||1,t=Math.max(0,Math.min(1,((p.x-e.a.x)*dx+(p.y-e.a.y)*dy)/l)),d=(p.x-e.a.x-t*dx)**2+(p.y-e.a.y-t*dy)**2;if(d<best){best=d;hit=e}});return hit}
    bind(){this.resizeObserver=new ResizeObserver(()=>this.resize());this.resizeObserver.observe(this.canvas.parentElement);this.canvas.addEventListener('wheel',e=>{e.preventDefault();const p=this.point(e),s=Math.max(.3,Math.min(5,this.scale*Math.exp(-e.deltaY*.001)));this.x=p.sx-p.x*s;this.y=p.sy-p.y*s;this.scale=s;this.draw()},{passive:false});this.canvas.addEventListener('pointerdown',e=>{const p=this.point(e),node=this.find(p);this.drag={sx:p.sx,sy:p.sy,x:this.x,y:this.y,node,edge:node?null:this.findEdge(p),moved:false};this.canvas.setPointerCapture(e.pointerId)});this.canvas.addEventListener('pointermove',e=>{const p=this.point(e);if(this.drag){this.drag.moved||=Math.hypot(p.sx-this.drag.sx,p.sy-this.drag.sy)>4;if(this.drag.node){this.drag.node.x=p.x;this.drag.node.y=p.y}else if(!this.drag.edge){this.x=this.drag.x+p.sx-this.drag.sx;this.y=this.drag.y+p.sy-this.drag.sy}this.draw()}else{this.hover=this.find(p);this.draw()}});this.canvas.addEventListener('pointerup',()=>{if(!this.drag?.moved&&this.drag?.node){this.selected=this.drag.node;this.selectedEdge=null;this.onPick({kind:'node',data:this.drag.node})}else if(!this.drag?.moved&&this.drag?.edge){this.selectedEdge=this.drag.edge;this.onPick({kind:'edge',data:this.drag.edge})}this.drag=null;this.draw()});this.canvas.addEventListener('pointerleave',()=>{if(!this.drag){this.hover=null;this.draw()}})}
    destroy(){cancelAnimationFrame(this.frame);this.resizeObserver.disconnect()}
    png(){return new Promise(resolve=>this.canvas.toBlob(resolve,'image/png'))}
    svg(){let minX=Math.min(...this.nodes.map(n=>n.x))-50,maxX=Math.max(...this.nodes.map(n=>n.x))+50,minY=Math.min(...this.nodes.map(n=>n.y))-50,maxY=Math.max(...this.nodes.map(n=>n.y))+50;return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${minX} ${minY} ${maxX-minX} ${maxY-minY}"><rect x="${minX}" y="${minY}" width="${maxX-minX}" height="${maxY-minY}" fill="${this.options.backgroundColor || '#10231d'}"/>${this.edges.map(e=>`<line x1="${e.a.x}" y1="${e.a.y}" x2="${e.b.x}" y2="${e.b.y}" stroke="${this.edgeColor(e)}" stroke-width="${this.edgeWidth(e)}" opacity=".6"/>`).join('')}${this.nodes.map(n=>`<g><circle cx="${n.x}" cy="${n.y}" r="${this.radius(n)}" fill="${n.unresolved?'#d9ff43':n.input?'#ff775f':color(n.community)}"/><text x="${n.x+this.radius(n)+5}" y="${n.y+3}" fill="${this.options.labelColor || '#ffffff'}" font-family="monospace" font-size="10">${esc(n.gene)}</text></g>`).join('')}</svg>`}
}

export default forwardRef(function CollectionNetworkCanvas({ graph, backgroundColor, labelColor, colors, widthMode, labels, nodeScale, onPick }, ref) {
    const canvas=useRef(null),renderer=useRef(null)
    useEffect(()=>{renderer.current=new Renderer(canvas.current,onPick);return()=>renderer.current.destroy()},[onPick])
    useEffect(()=>renderer.current?.setGraph(graph,{colors,widthMode,labels,nodeScale}),[graph,colors,widthMode,labels,nodeScale])
    useEffect(()=>{if(renderer.current){renderer.current.options.backgroundColor=backgroundColor;renderer.current.options.labelColor=labelColor;renderer.current.draw()}},[graph,colors,widthMode,labels,nodeScale,backgroundColor,labelColor])
    useImperativeHandle(ref,()=>({fit:()=>renderer.current.fit(),rearrange:()=>renderer.current.rearrange(),focus:q=>renderer.current.focus(q),separate:()=>renderer.current.separate(),svg:()=>renderer.current.svg(),png:()=>renderer.current.png(),pngDataURL:()=>renderer.current.canvas.toDataURL('image/png')}),[])
    return <canvas ref={canvas} aria-label="Interactive protein interaction network" />
})
