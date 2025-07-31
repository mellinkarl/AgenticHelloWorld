import { useState } from "react";

export default function App() {
  const [file, setFile] = useState(null);
  const [gcsURI, setGcsURI] = useState("");
  const [prompt, setPrompt] = useState("");
  const [response, setResponse] = useState("");

  const upload = async () => {
    const formData = new FormData();
    formData.append("file", file);
    const res = await fetch(process.env.REACT_APP_INGESTION_URL + "/ingest", {
      method: "POST",
      body: formData,
    });
    console.log(
      "Uploading to",
      process.env.REACT_APP_INGESTION_URL + "/ingest"
    );
    const data = await res.json();
    setGcsURI(data.uri);
  };

  const ask = async () => {
    const res = await fetch(process.env.REACT_APP_INGESTION_URL + "/query", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ prompt, gcs_uri: gcsURI }),
    });

    const data = await res.json();
    setResponse(data.response);
  };

  return (
    <div style={{ padding: 20 }}>
      <h1>Upload Manuscript</h1>
      <input type="file" onChange={(e) => setFile(e.target.files[0])} />
      <button onClick={upload}>Upload</button>
      {gcsURI && (
        <>
          <h2>Ask About the File</h2>
          <input
            type="text"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="Ask a question..."
            style={{ width: "300px" }}
          />
          <button onClick={ask}>Ask</button>
          <p>
            <strong>Response:</strong> {response}
          </p>
        </>
      )}
    </div>
  );
}
