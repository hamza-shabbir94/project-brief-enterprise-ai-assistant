import { useEffect, useRef, useState } from "react";
import { askQuestion } from "./api.js";
import ChatInput from "./components/ChatInput.jsx";
import { BotLogo, PlusIcon } from "./components/Icons.jsx";
import Message from "./components/Message.jsx";
import Welcome from "./components/Welcome.jsx";

export default function App() {
  // Each message: { id, role: "user" | "assistant", content, sources?, error?, question? }
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const conversationRef = useRef(null);
  const bottomRef = useRef(null);

  // Keep the newest message in view. After "New chat", go back to the top.
  useEffect(() => {
    if (messages.length === 0) conversationRef.current?.scrollTo(0, 0);
    else bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  function addMessage(message) {
    setMessages((previous) => [...previous, { id: crypto.randomUUID(), ...message }]);
  }

  async function send(question) {
    if (loading) return;
    addMessage({ role: "user", content: question });
    setLoading(true);
    try {
      const data = await askQuestion(question);
      addMessage({ role: "assistant", content: data.answer, sources: data.sources });
    } catch (error) {
      addMessage({ role: "assistant", error: error.message, question });
    } finally {
      setLoading(false);
    }
  }

  function retry(failedMessage) {
    // Remove the failed question and its error, then ask again.
    setMessages((previous) => previous.slice(0, -2));
    send(failedMessage.question);
  }

  return (
    <div className="app">
      <header className="header">
        <div className="brand">
          <BotLogo />
          <div>
            <div className="brand-name">IronStore Assistant</div>
            <div className="brand-sub">Internal knowledge base</div>
          </div>
        </div>
        {messages.length > 0 && (
          <button className="new-chat" onClick={() => setMessages([])} disabled={loading}>
            <PlusIcon /> New chat
          </button>
        )}
      </header>

      <main className="conversation" ref={conversationRef}>
        <div className="conversation-inner">
          {messages.length === 0 ? (
            <Welcome onPick={send} />
          ) : (
            messages.map((message) => <Message key={message.id} message={message} onRetry={retry} />)
          )}

          {loading && (
            <div className="message assistant">
              <div className="bubble thinking">
                <span className="dots"><i /><i /><i /></span>
                Searching company documents…
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>
      </main>

      <footer className="footer">
        <ChatInput onSend={send} disabled={loading} />
        <p className="disclaimer">
          Answers come from internal documents and can contain mistakes. Check the sources before acting on important decisions.
        </p>
      </footer>
    </div>
  );
}
