import { useState } from "react";

export default function App() {
  const [file, setFile] = useState(null);
  const [result, setResult] = useState("");

  const upload = async () => {
    const formData = new FormData();
    formData.append("file", file);
    const res = await fetch(process.env.REACT_APP_INGESTION_URL + "/ingest", {
      method: "POST",
      body: formData,
    });
    const data = await res.json();
    setResult(data.uri);
  };

  return (
    <div style={{ padding: 20 }}>
      <h1>Upload Manuscript:</h1>
      <input type="file" onChange={(e) => setFile(e.target.files[0])} />
      <button onClick={upload}>Upload</button>
      <p>{result}</p>
    </div>
  );
}
