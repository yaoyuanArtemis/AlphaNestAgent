import React, { useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

const API_URL = "http://127.0.0.1:8000";

function createSessionId() {
  if (crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function App() {
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      content:
        "Ask me about US stocks, recent price action, or market opportunities. I can fetch historical prices when needed.",
    },
  ]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const sessionIdRef = useRef(createSessionId());
  const canSend = useMemo(() => input.trim().length > 0 && !isLoading, [input, isLoading]);

  async function sendMessage(event) {
    event.preventDefault();
    if (!canSend) return;

    const userMessage = input.trim();
    setInput("");
    setIsLoading(true);
    setMessages((current) => [...current, { role: "user", content: userMessage }]);

    try {
      const response = await fetch(`${API_URL}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionIdRef.current,
          message: userMessage,
        }),
      });

      const payload = await response.json();
      if (!response.ok) {
        throw new Error(JSON.stringify(payload.error ?? payload, null, 2));
      }

      sessionIdRef.current = payload.session_id;
      setMessages((current) => [...current, { role: "assistant", content: payload.reply }]);
    } catch (error) {
      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          content: `Request failed:\n${error.message}`,
          isError: true,
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  }

  async function resetChat() {
    await fetch(`${API_URL}/reset`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionIdRef.current }),
    }).catch(() => {});

    sessionIdRef.current = createSessionId();
    setMessages([
      {
        role: "assistant",
        content:
          "Session reset. Ask me about a ticker such as RKLB, NVDA, AAPL, or a broader US market setup.",
      },
    ]);
  }

  return (
    <main className="app-shell">
      <section className="workspace">
        <header className="topbar">
          <div>
            <h1>AlphaNestAgent</h1>
            <p>US stock research assistant</p>
          </div>
          <button className="secondary-button" type="button" onClick={resetChat}>
            Reset
          </button>
        </header>

        <div className="messages" aria-live="polite">
          {messages.map((message, index) => (
            <article
              className={`message ${message.role === "user" ? "message-user" : "message-agent"} ${
                message.isError ? "message-error" : ""
              }`}
              key={`${message.role}-${index}`}
            >
              <div className="message-label">{message.role === "user" ? "You" : "AlphaNestAgent"}</div>
              <div className="message-content">{message.content}</div>
            </article>
          ))}
          {isLoading && (
            <article className="message message-agent">
              <div className="message-label">AlphaNestAgent</div>
              <div className="message-content">Thinking...</div>
            </article>
          )}
        </div>

        <form className="composer" onSubmit={sendMessage}>
          <textarea
            value={input}
            onChange={(event) => setInput(event.target.value)}
            placeholder="Ask about RKLB, NVDA, earnings risk, or recent price action..."
            rows={3}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                sendMessage(event);
              }
            }}
          />
          <button type="submit" disabled={!canSend}>
            Send
          </button>
        </form>
      </section>
    </main>
  );
}

createRoot(document.getElementById("root")).render(<App />);
