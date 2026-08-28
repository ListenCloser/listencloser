from pathlib import Path
import re

# Inspector: use the same accessible tab grammar as representation switching.
inspector = Path("components/workspace/Inspector.tsx")
text = inspector.read_text()
import_anchor = 'import AskPanel from "./AskPanel";\n'
if 'import TabStrip from "@/components/ui/TabStrip";' not in text:
    if import_anchor not in text:
        raise SystemExit("Inspector import anchor not found")
    text = text.replace(
        import_anchor,
        'import TabStrip from "@/components/ui/TabStrip";\n' + import_anchor,
        1,
    )

old_tabs = '''        <nav className="inspector-mode-tabs" role="tablist" aria-label="Inspector mode">
          <button type="button" role="tab" aria-selected={mode === "analysis"} className={mode === "analysis" ? "active" : ""} onClick={() => setInspectorMode("analysis")}>Analysis</button>
          <button type="button" role="tab" aria-selected={mode === "ask"} className={mode === "ask" ? "active" : ""} onClick={() => setInspectorMode("ask")}>Ask</button>
        </nav>'''
new_tabs = '''        <TabStrip
          className="inspector-mode-tabs"
          label="Inspector mode"
          items={[
            { id: "analysis", label: "Analysis" },
            { id: "ask", label: "Ask" },
          ]}
          value={mode}
          onChange={setInspectorMode}
        />'''
if old_tabs not in text:
    raise SystemExit("Inspector tab block not found")
text = text.replace(old_tabs, new_tabs, 1)
inspector.write_text(text)

# Transport: replace the one-off source popover with keyboard-complete shared listbox.
transport = Path("components/workspace/TransportBar.tsx")
text = transport.read_text()
text = text.replace(
    'import { useEffect, useRef, useState } from "react";\n',
    'import ListboxMenu from "@/components/ui/ListboxMenu";\n',
    1,
)
pattern = re.compile(r'\nfunction SourceMenu\(\{.*?\n\}\n\nfunction CompareTransportControl\(\)', re.S)
match = pattern.search(text)
if not match:
    raise SystemExit("Transport SourceMenu block not found")
text = text[:match.start()] + '\nfunction CompareTransportControl()' + text[match.end():]
text = text.replace("<SourceMenu", "<ListboxMenu")
transport.write_text(text)
