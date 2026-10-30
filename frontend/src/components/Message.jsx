import { useState } from "react";
import ReactMarkdown from "react-markdown";
import { AlertIcon, ChevronIcon, FileIcon } from "./Icons.jsx";

// The LLM cites sources like [1] or [2][4]. Find which numbers it used.
function citedNumbers(answer) {
  return new Set([...answer.matchAll(/\[(\d+)\]/g)].map((match) => Number(match[1])));
}

// Turn "[2]" into a markdown link "[2](#cite-2)" so we can render it as a clickable chip.
function linkCitations(answer) {
  return answer.replace(/\[(\d+)\](?!\()/g, "[$1](#cite-$1)");
}

function SourceCard({ source, highlighted }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <li id={`source-${source.number}`} className={`source ${highlighted ? "highlighted" : ""}`}>
      <div className="source-head">
        <span className="source-number">{source.number}</span>
        <div className="source-meta">
          <span className="source-title">
            <FileIcon /> {source.title}
          </span>
          <span className="source-details">
            Page {source.page} · {source.department.replaceAll("_", " ")} · Reviewed {source.last_reviewed}
          </span>
        </div>
        <button className="link-button" onClick={() => setExpanded(!expanded)}>
          {expanded ? "Hide" : "Show"} text
        </button>
      </div>
      {expanded && <p className="source-excerpt">{source.excerpt}…</p>}
    </li>
  );
}

function AssistantAnswer({ message }) {
  const cited = citedNumbers(message.content);
  const [open, setOpen] = useState(false);
  const [showAll, setShowAll] = useState(false);
  const [highlight, setHighlight] = useState(null);

  // Show only the sources the answer actually used, unless the user asks for all.
  // If it used none (e.g. "I couldn't find it"), show what was searched instead.
  const usedNone = cited.size === 0;
  const usedAll = cited.size === message.sources.length;
  const visibleSources =
    showAll || usedNone ? message.sources : message.sources.filter((s) => cited.has(s.number));
  const plural = cited.size > 1 ? "s" : "";
  const toggleLabel = usedNone
    ? `No sources used · ${message.sources.length} passages searched`
    : `${cited.size} source${plural} used`;

  function openSource(number) {
    setOpen(true);
    setHighlight(number);
    // Wait for the list to render, then scroll the card into view.
    setTimeout(() => document.getElementById(`source-${number}`)?.scrollIntoView({ behavior: "smooth", block: "nearest" }), 50);
  }

  const markdownComponents = {
    a: ({ href, children }) =>
      href?.startsWith("#cite-") ? (
        <button className="cite" onClick={() => openSource(Number(href.slice(6)))} title="Show source">
          {children}
        </button>
      ) : (
        <a href={href} target="_blank" rel="noreferrer">{children}</a>
      ),
  };

  return (
    <>
      <div className="markdown">
        <ReactMarkdown components={markdownComponents}>{linkCitations(message.content)}</ReactMarkdown>
      </div>

      {message.sources.length > 0 && (
        <div className="sources">
          <button className="sources-toggle" onClick={() => setOpen(!open)} aria-expanded={open}>
            <ChevronIcon open={open} />
            {toggleLabel}
          </button>
          {open && (
            <>
              <ul className="source-list">
                {visibleSources.map((source) => (
                  <SourceCard key={source.number} source={source} highlighted={highlight === source.number} />
                ))}
              </ul>
              {!usedNone && !usedAll && (
                <button className="link-button" onClick={() => setShowAll(!showAll)}>
                  {showAll ? "Show only cited sources" : `Show all ${message.sources.length} retrieved passages`}
                </button>
              )}
            </>
          )}
        </div>
      )}
    </>
  );
}

export default function Message({ message, onRetry }) {
  if (message.role === "user") {
    return (
      <div className="message user">
        <div className="bubble">{message.content}</div>
      </div>
    );
  }

  return (
    <div className="message assistant">
      <div className="bubble">
        {message.error ? (
          <div className="error">
            <AlertIcon />
            <span>{message.error}</span>
            <button className="link-button" onClick={() => onRetry(message)}>Try again</button>
          </div>
        ) : (
          <AssistantAnswer message={message} />
        )}
      </div>
    </div>
  );
}
