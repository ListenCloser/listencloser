"use client";

import { useMemo, useState } from "react";
import styles from "./option-a.module.css";

type Stage = "landing" | "library" | "processing" | "workspace";
type View = "waveform" | "piano" | "score" | "spectrogram";
type Inspector = "breakdown" | "ask" | "compare";

const waveform = [22,34,18,42,52,36,28,61,48,30,66,54,24,40,58,32,70,64,38,26,55,46,31,62,49,35,69,44,28,57,72,41,33,60,50,27,65,53,36,43,68,47,29,59,51,39,63,45,30,56,71,37,25,52,67,40,34,58,48,32];
const notes = [[2,18,10],[8,14,18],[12,22,28],[18,10,38],[23,26,46],[31,15,34],[35,20,22],[42,12,52],[47,28,58],[56,16,42],[61,20,30],[68,11,18],[73,17,34],[79,9,44],[84,12,24]] as const;

export default function OptionAFlow() {
  const [stage, setStage] = useState<Stage>("landing");
  const [view, setView] = useState<View>("waveform");
  const [inspector, setInspector] = useState<Inspector>("breakdown");
  const [selected, setSelected] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [looping, setLooping] = useState(false);
  const [processingStep, setProcessingStep] = useState(1);
  const [query, setQuery] = useState("");

  const context = useMemo(() => selected ? "01:14–01:31" : "whole recording", [selected]);

  if (stage === "landing") {
    return (
      <main className={styles.landing}>
        <header className={styles.landingBar}><Brand /><button className={styles.ghost} onClick={() => setStage("library")}>Open workspace</button></header>
        <section className={styles.hero}>
          <div className={styles.heroCopy}>
            <p className={styles.kicker}>LISTEN · SEE · UNDERSTAND</p>
            <h1>Hear the same moment<br/>from more than one angle.</h1>
            <p className={styles.heroBody}>Move through audio, notation, pitch, structure, and evidence without losing your place in the music.</p>
            <button className={styles.primary} onClick={() => setStage("library")}>Start with a recording <span>→</span></button>
          </div>
          <div className={styles.heroObject} aria-label="Shared musical time illustration">
            <div className={styles.heroTime}>01:14.2</div>
            <div className={styles.heroWave}>{waveform.slice(0,32).map((h,i)=><i key={i} style={{height:`${h}%`}} />)}</div>
            <div className={styles.heroAxis}/>
            <div className={styles.heroNotes}>{notes.slice(0,8).map(([x,w,y],i)=><b key={i} style={{left:`${x}%`,width:`${Math.max(5,w/2)}%`,top:`${y}%`}} />)}</div>
            <p>one moment · many truthful views</p>
          </div>
        </section>
      </main>
    );
  }

  if (stage === "library") {
    return (
      <main className={styles.libraryScreen}>
        <header className={styles.appBar}><Brand/><span className={styles.path}>LIBRARY</span><button className={styles.ghost} onClick={() => setStage("landing")}>Back to landing</button></header>
        <section className={styles.libraryHero}>
          <div><p className={styles.kicker}>YOUR MUSIC</p><h1>Start with what you actually want to understand.</h1><p>No project setup. Import a recording; ListenCloser keeps every representation anchored to it.</p></div>
          <button className={styles.importButton} onClick={() => setStage("processing")}><span>＋</span><strong>Import a recording</strong><small>audio or video</small></button>
        </section>
        <section className={styles.recordings}>
          <div className={styles.sectionHead}><span>RECENT</span><span>3 recordings</span></div>
          {[['Moon River','Henry Mancini','2:43'],['Autumn Leaves','Cannonball Adderley','5:32'],['Blue in Green','Miles Davis','5:37']].map((r,i)=><button key={r[0]} className={styles.recordingRow} onClick={() => { if(i===0) setStage("workspace"); }}><span className={styles.rowIndex}>0{i+1}</span><span className={styles.rowWave}>{waveform.slice(i*10,i*10+18).map((h,j)=><i key={j} style={{height:`${h}%`}}/>)}</span><span><strong>{r[0]}</strong><small>{r[1]}</small></span><span className={styles.duration}>{r[2]}</span><span>→</span></button>)}
        </section>
      </main>
    );
  }

  if (stage === "processing") {
    const steps = ["Audio ready","Transcribing notes","Locating musical time","Preparing evidence"];
    return (
      <main className={styles.processingScreen}>
        <header className={styles.appBar}><Brand/><span className={styles.path}>IMPORT</span><button className={styles.ghost} onClick={() => setStage("library")}>Cancel</button></header>
        <section className={styles.processingBody}>
          <div className={styles.processingSignal}>{waveform.map((h,i)=><i key={i} style={{height:`${h}%`}}/>)}</div>
          <p className={styles.kicker}>MOON RIVER · 02:43</p>
          <h1>Building views of the recording.</h1>
          <div className={styles.pipeline}>{steps.map((s,i)=><button key={s} onClick={() => setProcessingStep(Math.max(processingStep,i+1))} className={i < processingStep ? styles.done : i === processingStep ? styles.current : ""}><span>{i < processingStep ? '✓' : `0${i+1}`}</span><strong>{s}</strong><small>{i < processingStep ? 'ready' : i === processingStep ? 'working' : 'queued'}</small></button>)}</div>
          <div className={styles.processingActions}>{processingStep < 4 ? <button className={styles.primary} onClick={() => setProcessingStep(s=>Math.min(4,s+1))}>Advance prototype step →</button> : <button className={styles.primary} onClick={() => setStage("workspace")}>Open the recording →</button>}</div>
        </section>
      </main>
    );
  }

  return (
    <main className={styles.shell}>
      <header className={styles.topbar}><Brand/><div className={styles.workTitle}><strong>Moon River</strong><small>Henry Mancini · 02:43</small></div><div className={styles.topActions}><button onClick={() => setStage("library")}>Library</button><button onClick={() => setInspector("compare")}>Compare</button><button>•••</button></div></header>
      <section className={styles.workspace}>
        <aside className={styles.leftRail}>
          <div className={styles.railHead}><span>RECORDINGS</span><button>＋</button></div>
          {[['Moon River','2:43'],['Autumn Leaves','5:32'],['Blue in Green','5:37']].map((r,i)=><button key={r[0]} className={i===0?styles.activeWork:""}><span className={styles.miniWave}>{waveform.slice(i*8,i*8+12).map((h,j)=><i key={j} style={{height:`${h}%`}}/>)}</span><span><strong>{r[0]}</strong><small>{r[1]}</small></span></button>)}
          <div className={styles.railFoot}>3 recordings</div>
        </aside>

        <section className={styles.canvas}>
          <nav className={styles.viewTabs}>{([['waveform','Waveform'],['piano','Piano roll'],['score','Score'],['spectrogram','Spectrogram']] as const).map(([id,label])=><button key={id} className={view===id?styles.activeTab:""} onClick={()=>setView(id)}>{label}</button>)}<span/><button className={styles.toolButton}>Fit</button><button className={styles.toolButton}>Grid</button></nav>
          <div className={styles.ruler}>{['0:00','0:20','0:40','1:00','1:20','1:40','2:00','2:20','2:43'].map(t=><span key={t}>{t}</span>)}</div>

          {view === "waveform" && <button className={styles.waveView} onClick={() => setSelected(v=>!v)} aria-label="Select passage in waveform"><div className={styles.centerLine}/>{waveform.map((h,i)=><i key={i} style={{height:`${h}%`}}/>)}{selected&&<div className={styles.selection}/>}<div className={styles.playhead}/><span className={styles.hint}>click waveform to {selected?'clear':'select'} passage</span></button>}
          {view === "piano" && <button className={styles.pianoView} onClick={() => setSelected(v=>!v)}><div className={styles.keys}>{['C6','C5','C4','C3','C2'].map(x=><span key={x}>{x}</span>)}</div><div className={styles.noteGrid}>{notes.map(([x,w,y],i)=><b key={i} style={{left:`${x}%`,width:`${w}%`,top:`${y}%`}}/>)}{selected&&<div className={styles.selection}/>}<div className={styles.playhead}/></div></button>}
          {view === "score" && <button className={styles.scoreView} onClick={() => setSelected(v=>!v)}><div className={styles.staff}>{[0,1,2,3,4].map(i=><i key={i}/>)}</div><div className={styles.scoreNotes}>♩ ♪ ♩. ♫ &nbsp;&nbsp; 𝄞 &nbsp; ♩ ♩ ♪ ♩</div>{selected&&<div className={styles.scoreSelection}/>}</button>}
          {view === "spectrogram" && <button className={styles.spectrumView} onClick={() => setSelected(v=>!v)}>{waveform.map((h,i)=><i key={i} style={{opacity:.2+(h/100)*.7,height:`${30+h}%`}}/>)}{selected&&<div className={styles.selection}/>}<div className={styles.playhead}/></button>}

          <div className={styles.canvasFoot}><span>{selected?`PASSAGE · ${context}`:'WHOLE RECORDING'}</span><span>shared musical time</span></div>
        </section>

        <aside className={styles.inspector}>
          <div className={styles.inspectorTabs}>{([['breakdown','Breakdown'],['ask','Ask']] as const).map(([id,label])=><button key={id} className={inspector===id?styles.activeInspector:""} onClick={()=>setInspector(id)}>{label}</button>)}</div>
          {inspector === "breakdown" && <>
            <section className={styles.insightLead}><small>{selected?'SELECTED PASSAGE':'AT 01:18.4'}</small><h2>{selected?'The phrase tightens before release.':'A new phrase arrives with less harmonic weight.'}</h2><p>{selected?'Melody rises while note density increases; the accompaniment holds the same harmonic center.':'The texture thins and the melody settles into a narrower register.'}</p></section>
            <section className={styles.evidence}><button><i className={styles.harmony}/><span><strong>Harmony</strong><small>Db major · observed</small></span><span>›</span></button><button><i className={styles.pitch}/><span><strong>Melody</strong><small>register rises · observed</small></span><span>›</span></button><button><i className={styles.rhythm}/><span><strong>Rhythm</strong><small>density +18% · measured</small></span><span>›</span></button></section>
            <button className={styles.askPassage} onClick={()=>setInspector("ask")}>Ask about {context} →</button>
          </>}
          {inspector === "ask" && <section className={styles.askPane}><p className={styles.kicker}>ASK · {context.toUpperCase()}</p><div className={styles.answer}>{query ? <><strong>Why does this moment feel more tense?</strong><p>Because the melody climbs while the accompaniment sustains the same harmonic center, increasing registral and rhythmic pressure without a harmonic reset.</p><small>Evidence: melody register · note density · harmony</small></> : <p>Ask about what you hear, what changed, or how this passage relates to another moment.</p>}</div><div className={styles.askInput}><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Why does this feel more tense?"/><button onClick={()=>setQuery(query||"Why does this feel more tense?")}>↑</button></div></section>}
          {inspector === "compare" && <section className={styles.comparePane}><p className={styles.kicker}>COMPARE</p><h2>Same passage, two takes.</h2><div className={styles.compareRows}><span>A · Moon River</span><b style={{width:'72%'}}/><span>B · Reference</span><b style={{width:'61%'}}/></div><p>The reference enters the phrase slightly later and sustains the melody longer.</p><button onClick={()=>setInspector("breakdown")}>Back to Breakdown</button></section>}
        </aside>
      </section>

      <footer className={styles.transport}><button onClick={()=>setPlaying(false)}>◀</button><button className={styles.play} onClick={()=>setPlaying(v=>!v)}>{playing?'Ⅱ':'▶'}</button><strong>01:18.4</strong><div className={styles.transportRail}><span/></div><span>02:43.0</span><button className={looping?styles.loopOn:""} onClick={()=>setLooping(v=>!v)}>LOOP</button><button>ORIGINAL⌄</button></footer>
    </main>
  );
}

function Brand(){return <div className={styles.brand}><span className={styles.mark}>◖</span><strong>LISTEN CLOSER</strong></div>}
