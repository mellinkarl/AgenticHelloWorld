import { useState } from "react";

export default function App() {
  const [file, setFile] = useState(null);

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
    console.log("Upload response:", data);
    if (data.uri) {
      setGcsURI(data.uri);
    } else {
      alert("Upload failed: " + data.error);
    }
  };

  return (
    <div style={{ padding: 20 }}>
      <h1>Upload Manuscript</h1>
      <input type="file" onChange={(e) => setFile(e.target.files[0])} />
      <button onClick={upload}>Upload</button>
    </div>
  );
}
