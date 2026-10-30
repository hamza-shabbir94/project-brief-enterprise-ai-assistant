import { useEffect, useRef, useState } from "react";
import { SendIcon } from "./Icons.jsx";

// Text box at the bottom. Enter sends, Shift+Enter adds a new line.
export default function ChatInput({ onSend, disabled }) {
  const [text, setText] = useState("");
  const textareaRef = useRef(null);

  // Grow the box with its content, up to a maximum height (set in CSS).
  useEffect(() => {
    const el = textareaRef.current;
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight}px`;
  }, [text]);

  function submit() {
    if (!text.trim() || disabled) return;
    onSend(text.trim());
    setText("");
  }

  function handleKeyDown(event) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      submit();
    }
  }

  return (
    <form
      className="chat-input"
      onSubmit={(event) => {
        event.preventDefault();
        submit();
      }}
    >
      <textarea
        ref={textareaRef}
        rows={1}
        value={text}
        maxLength={1000}
        placeholder="Ask a question about IronStore…"
        aria-label="Your question"
        onChange={(event) => setText(event.target.value)}
        onKeyDown={handleKeyDown}
        autoFocus
      />
      <button type="submit" className="send-button" disabled={disabled || !text.trim()} aria-label="Send">
        <SendIcon />
      </button>
    </form>
  );
}
