// Shown before the first question: a greeting plus example questions to click.

const EXAMPLES = [
  { area: "HR", question: "What is our remote work policy?" },
  { area: "HR", question: "How do I request time off?" },
  { area: "Customer support", question: "What is the return policy for customers?" },
  { area: "Finance", question: "How do I submit an expense claim?" },
  { area: "Products", question: "How much does the Nordview NQ-55U7 TV cost and is it in stock?" },
  { area: "IT", question: "What are the password requirements?" },
];

export default function Welcome({ onPick }) {
  return (
    <div className="welcome">
      <h1>How can I help today?</h1>
      <p className="welcome-sub">
        Ask about company policies, procedures or products. Every answer links to the internal
        documents it comes from.
      </p>
      <div className="examples">
        {EXAMPLES.map((example) => (
          <button key={example.question} className="example" onClick={() => onPick(example.question)}>
            <span className="example-area">{example.area}</span>
            <span>{example.question}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
