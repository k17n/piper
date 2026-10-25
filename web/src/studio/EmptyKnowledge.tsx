import { Button } from "../components/ui";
import { KNOWLEDGE_FILES } from "./knowledge";
import { useStudio } from "./store";

/** First run: the studio writes from the user's own notes, so it asks for them before anything else. */
export function EmptyKnowledge() {
  const { setKnowledgeReady, toast } = useStudio();
  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-5 px-4 py-10">
      <div>
        <h2 className="text-lg font-semibold text-ink">Start with your notes</h2>
        <p className="mt-1 text-sm leading-relaxed text-ink-2">
          The writing studio only writes from what you give it: your résumé, strengths, projects and stories. Everything stays on this computer, and every
          sentence it writes points back to the note it came from.
        </p>
      </div>

      <section aria-label="Files to add" className="card p-3">
        <h3 className="px-1 pb-2 text-sm font-semibold text-ink">Put these in your knowledge folder</h3>
        <ul className="divide-y divide-line">
          {KNOWLEDGE_FILES.map((f) => (
            <li key={f.path} className="flex items-baseline gap-3 px-1 py-2">
              <code className="w-28 shrink-0 text-sm text-ink">{f.path}</code>
              <span className="min-w-0 flex-1 text-sm text-ink-2">{f.what}</span>
              <span className="shrink-0 text-xs text-ink-2">{f.core ? "Start here" : "Later"}</span>
            </li>
          ))}
        </ul>
        <p className="px-1 pt-2 text-xs text-ink-2">Plain Markdown files. Rough notes are fine.</p>
      </section>

      <div className="flex flex-wrap gap-2">
        <Button variant="primary" onClick={() => toast("Prototype: the folder picker isn't built yet.")}>
          Choose my knowledge folder
        </Button>
        <Button variant="outline" onClick={() => setKnowledgeReady(true)}>
          Try it with sample notes
        </Button>
      </div>
    </div>
  );
}
