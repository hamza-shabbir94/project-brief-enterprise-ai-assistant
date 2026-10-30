// Small inline SVG icons, so we don't need an icon library.

const base = {
  width: 18,
  height: 18,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 2,
  strokeLinecap: "round",
  strokeLinejoin: "round",
  "aria-hidden": true,
};

export const SendIcon = () => (
  <svg {...base}><path d="M5 12h14M13 6l6 6-6 6" /></svg>
);

export const PlusIcon = () => (
  <svg {...base}><path d="M12 5v14M5 12h14" /></svg>
);

export const ChevronIcon = ({ open }) => (
  <svg {...base} style={{ transform: open ? "rotate(180deg)" : "none", transition: "transform .2s" }}>
    <path d="m6 9 6 6 6-6" />
  </svg>
);

export const FileIcon = () => (
  <svg {...base}><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" /><path d="M14 3v5h5" /></svg>
);

export const AlertIcon = () => (
  <svg {...base}><circle cx="12" cy="12" r="9" /><path d="M12 8v4M12 16h.01" /></svg>
);

export const BotLogo = ({ size = 32 }) => (
  <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true">
    <rect width="32" height="32" rx="9" fill="var(--accent)" />
    <rect x="8" y="10" width="16" height="12" rx="4" fill="var(--on-accent)" />
    <circle cx="13" cy="16" r="1.8" fill="var(--accent)" />
    <circle cx="19" cy="16" r="1.8" fill="var(--accent)" />
    <rect x="15" y="5" width="2" height="5" rx="1" fill="var(--on-accent)" />
  </svg>
);
