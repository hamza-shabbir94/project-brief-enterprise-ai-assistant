// All communication with the backend lives here.

export async function askQuestion(question) {
  const response = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });

  if (!response.ok) {
    let message = "Something went wrong. Please try again.";
    try {
      const data = await response.json();
      if (typeof data.detail === "string") message = data.detail;
    } catch {
      // The response wasn't JSON (e.g. the server is down). Keep the default message.
    }
    throw new Error(message);
  }

  return response.json(); // { answer, sources }
}
