"use client";

import { useState } from "react";
import type { SiteContent } from "@/content/types";

/** Small client-side island: changing the selected phase never requests the backend. */
export function IdeaVisual({ visual }: { visual: SiteContent["visual"] }) {
  const [selected, setSelected] = useState(1);
  return (
    <div className="idea-visual" aria-label={visual.title}>
      <div className="idea-topline"><span className="live-dot" />{visual.eyebrow}<span className="visual-dots" aria-hidden="true"><i/><i/><i/></span></div>
      <div className="orbit-stage" aria-hidden="true">
        <div className="orbit orbit-outer"/><div className="orbit orbit-middle"/><div className="orbit orbit-inner"/>
        <svg className="orbit-lines" viewBox="0 0 380 330" fill="none" preserveAspectRatio="xMidYMid meet"><path d="M78 165C132 93 232 95 300 165" stroke="#80BFA4" strokeWidth="1.5" strokeDasharray="6 8"/><path d="M78 165C140 248 246 246 300 165" stroke="#9DCFB9" strokeWidth="1.5" strokeDasharray="4 8"/><path d="M190 63v204" stroke="#A9D9C6" strokeDasharray="4 9"/></svg>
        <div className="orbit-core"><span className="core-spark">✳</span><strong>meraki</strong><small dir="auto">{visual.coreLabel}</small></div>
        <span className="orbit-satellite satellite-one">✦</span><span className="orbit-satellite satellite-two">✧</span><span className="orbit-satellite satellite-three">+</span>
      </div>
      <div className="visual-content"><div><span className="visual-kicker">0{selected + 1} / 03</span><h3>{visual.title}</h3></div><p aria-live="polite">{visual.descriptions[selected]}</p></div>
      <div className="phase-switcher" aria-label={visual.title}>
        {visual.phases.map((phase, i) => <button key={phase} type="button" onClick={() => setSelected(i)} aria-pressed={selected === i} className={`phase-button ${selected === i ? "phase-active" : ""}`}><span className="phase-number">0{i + 1}</span><span>{phase}</span></button>)}
      </div>
      <div className="visual-footer">{visual.note}</div>
    </div>
  );
}
