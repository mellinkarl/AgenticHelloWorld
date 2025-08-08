import { useState } from "react";

export default function App() {
  const [file, setFile] = useState(null);
  const [resp, setResp] = useState(null);

  const upload = async () => {
    console.log(
      "Uploading to",
      process.env.REACT_APP_INGESTION_URL + "/ingest"
    );
    const formData = new FormData();
    formData.append("file", file);
    const res = await fetch(process.env.REACT_APP_INGESTION_URL + "/ingest", {
      method: "POST",
      body: formData,
    });

    const data = await res.json();
    if (!res.ok) {
      return alert(data.error || "Upload failed");
    }
    setResp(data);
  };

  return (
    <div style={{ padding: 20 }}>
      <h1>Upload Manuscript</h1>
      <input type="file" onChange={(e) => setFile(e.target.files[0])} />
      <button onClick={upload}>Upload</button>

      {resp && (
        <pre
          style={{
            marginTop: 16,
            background: "#111",
            color: "#eee",
            padding: 12,
          }}
        >
          {JSON.stringify(resp, null, 2)}
        </pre>
      )}
    </div>
  );
}
