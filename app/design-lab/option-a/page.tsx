import styles from "./option-a.module.css";

const bars = [22,34,18,42,52,36,28,61,48,30,66,54,24,40,58,32,70,64,38,26,55,46,31,62,49,35,69,44,28,57,72,41,33,60,50,27,65,53,36,43,68,47,29,59,51,39,63,45,30,56,71,37,25,52,67,40,34,58,48,32];
const notes = [
  [2,18,6],[8,14,10],[12,22,14],[18,10,18],[23,26,22],[31,15,26],[35,20,30],[42,12,34],[47,28,38],[56,16,42],[61,20,46],[68,11,50],[73,17,54],[79,9,58],[84,22,62]
] as const;

function Icon({ children }: { children: React.ReactNode }) {
  return <span className={styles.icon}>{children}</span>;
}

export default function OptionAMockup() {
  return (
    <main className={styles.shell}>
      <header className={styles.topbar}>
        <div className={styles.brand}><span className={styles.mark}>◖</span><strong>LISTEN CLOSER</strong></div>
        <div className={styles.workTitle}><span>NOCTURNE · TAKE 03</span><small>performance · 04:18</small></div>
        <div className={styles.headerMeta}><span className={styles.statusDot}/>READY <button>···</button></div>
      </header>

      <section className={styles.workspace}>
        <aside className={styles.library}>
          <div className={styles.panelHead}><span>LIBRARY</span><button>＋</button></div>
          <div className={styles.search}>⌕&nbsp;&nbsp;Search recordings</div>
          <nav className={styles.workList}>
            <button className={styles.activeWork}><span>03</span><div><strong>Nocturne · Take 03</strong><small>Today · 04:18</small></div></button>
            <button><span>02</span><div><strong>Nocturne · Take 02</strong><small>Today · 04:21</small></div></button>
            <button><span>01</span><div><strong>Nocturne · Take 01</strong><small>Yesterday · 04:16</small></div></button>
            <button><span>R</span><div><strong>Reference recording</strong><small>Aug 28 · 04:11</small></div></button>
          </nav>
          <div className={styles.libraryFooter}><span>4 RECORDINGS</span><button>IMPORT</button></div>
        </aside>

        <section className={styles.canvas}>
          <div className={styles.viewTabs}>
            <button className={styles.activeTab}>WAVEFORM</button><button>PIANO ROLL</button><button>SCORE</button><button>SPECTRUM</button>
            <span className={styles.flex}/><button className={styles.micro}>GRID</button><button className={styles.micro}>FIT</button>
          </div>

          <div className={styles.ruler}>{[0,30,60,90,120,150,180,210,240].map((n)=><span key={n}>{Math.floor(n/60)}:{String(n%60).padStart(2,"0")}</span>)}</div>

          <div className={styles.wavePanel}>
            <div className={styles.waveLabel}><span>AUDIO</span><strong>L+R</strong></div>
            <div className={styles.waveform}>
              {bars.map((h,i)=><i key={i} style={{height:`${h}%`}} />)}
              <div className={styles.selection}/><div className={styles.playhead}/>
            </div>
          </div>

          <div className={styles.divider}><span>SHARED MUSICAL TIME</span><span>01:42.8</span></div>

          <div className={styles.rollPanel}>
            <div className={styles.keyboard}>{["C6","C5","C4","C3"].map(x=><span key={x}>{x}</span>)}</div>
            <div className={styles.rollGrid}>
              {[0,1,2,3,4,5,6,7].map(x=><i key={`v${x}`} className={styles.vline} style={{left:`${x*12.5}%`}}/>)}
              {[0,1,2,3,4,5,6,7,8,9,10,11].map(y=><i key={`h${y}`} className={styles.hline} style={{top:`${y*8.33}%`}}/>)}
              {notes.map(([x,w,y],i)=><b key={i} className={styles.note} style={{left:`${x}%`,width:`${w}%`,top:`${y}%`}}/>)}
              <div className={styles.rollSelection}/><div className={styles.playhead}/>
            </div>
          </div>
        </section>

        <aside className={styles.inspector}>
          <div className={styles.inspectorTabs}><button className={styles.activeInspector}>BREAKDOWN</button><button>ASK</button></div>
          <section className={styles.now}><small>AT 01:42.8</small><h2>Harmonic tension increases.</h2><p>The left hand sustains the dominant while the melody reaches its highest register in this phrase.</p></section>
          <section className={styles.evidence}><div className={styles.evidenceHead}><span>EVIDENCE</span><span>3</span></div>
            <button><i className={styles.harmony}/> <div><strong>Harmony</strong><small>Dominant function · measured</small></div><span>›</span></button>
            <button><i className={styles.pitch}/> <div><strong>Register</strong><small>Melody peak · observed</small></div><span>›</span></button>
            <button><i className={styles.rhythm}/> <div><strong>Rhythm</strong><small>Density +18% · measured</small></div><span>›</span></button>
          </section>
          <section className={styles.actions}><button>LOOP PASSAGE</button><button>ASK ABOUT THIS</button></section>
        </aside>
      </section>

      <footer className={styles.transport}>
        <button><Icon>↶</Icon></button><button className={styles.play}><Icon>▶</Icon></button><button><Icon>↷</Icon></button>
        <strong>01:42.8</strong><div className={styles.transportRail}><span/></div><span>04:18.2</span>
        <div className={styles.transportRight}><button>1×</button><button>LOOP</button><button>ORIGINAL⌄</button></div>
      </footer>
    </main>
  );
}
