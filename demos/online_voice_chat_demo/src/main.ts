import "./style.css";
import { RealtimeAgent, RealtimeSession } from "@openai/agents-realtime";

const app = document.querySelector<HTMLDivElement>("#app")!;
app.innerHTML = `
  <h1>Realtime Agent Demo</h1>
  <button id="connect-btn">Connect to Realtime Agent</button>
  <p id="status">Status: Not connected</p>
  <div id="chat-ui" style="display:none;">
    <input id="user-input" type="text" placeholder="Type a message..." />
    <button id="send-btn">Send</button>
    <div id="messages" style="margin-top:1em; white-space:pre-wrap;"></div>
  </div>
`;

let session: RealtimeSession | null = null;

async function connectAgent() {
  const statusEl = document.querySelector<HTMLParagraphElement>("#status")!;
  statusEl.textContent = "Status: Fetching token...";

  try {
    const resp = await fetch("http://localhost:3000/session");
    const data = await resp.json();
    // spport structure
    const clientKey = data?.client_secret?.value ?? data?.value;

    if (!clientKey) {
      statusEl.textContent = "Status: No client key in response";
      console.error("Token response object:", data);
      return;
    }

    const agent = new RealtimeAgent({
      name: "Assistant",
      instructions: "You are a helpful assistant.",
    });

    session = new RealtimeSession(agent, {
      model: "gpt-4o-mini-realtime-preview-2024-12-17",
    });

    statusEl.textContent = "Status: Connecting to Realtime...";
    await session.connect({ apiKey: clientKey });

    console.log("✅ Realtime session connected!");
    statusEl.textContent = "Status: Connected ✅";

    // chatbox UI
    (document.querySelector<HTMLDivElement>("#chat-ui")!).style.display = "block";
  } catch (err) {
    console.error("❌ Failed to connect:", err);
    statusEl.textContent = "Status: Failed to connect ❌";
  }
}

async function sendMessage() {
  if (!session) return;
  const inputEl = document.querySelector<HTMLInputElement>("#user-input")!;
  const msgBox = document.querySelector<HTMLDivElement>("#messages")!;
  const text = inputEl.value.trim();
  if (!text) return;

  // user input
  msgBox.innerHTML += `\n👤 You: ${text}`;

  inputEl.value = "";

  try {
    // send message to model
    const reply = await session.send({
      type: "message",
      role: "user",
      content: text,
    });

    // get sreuctureed return
    if (reply?.output_text) {
      msgBox.innerHTML += `\n🤖 Assistant: ${reply.output_text}`;
    } else {
      msgBox.innerHTML += `\n🤖 Assistant: (no text output)`;
    }
  } catch (err) {
    console.error("Send failed:", err);
    msgBox.innerHTML += `\n❌ Error sending message`;
  }
}

document
  .querySelector<HTMLButtonElement>("#connect-btn")!
  .addEventListener("click", connectAgent);

document
  .querySelector<HTMLButtonElement>("#send-btn")!
  .addEventListener("click", sendMessage);
