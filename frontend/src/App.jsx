import { useState } from "react";
import "./App.css";

const API_BASE = import.meta.env.VITE_API_URL;

// Upload Helper
async function uploadFile(file, setResult, setLoading) {
  setLoading(true);

  const formData = new FormData();
  formData.append("file", file);

  try {
    const res = await fetch(`${API_BASE}/upload`, {
      method: "POST",
      body: formData,
    });

    if (!res.ok) {
      const text = await res.text();
      throw new Error(text);
    }

    const data = await res.json();
    setResult(data);
  } catch (err) {
    alert("Upload failed");
    console.error(err);
  } finally {
    setLoading(false);
  }
}

// Review Form
function ReviewForm({ data }) {
  const [title, setTitle] = useState(data.program_title);
  const [startDate, setStartDate] = useState(data.start_date);
  const [endDate, setEndDate] = useState(data.end_date);
  const [venue, setVenue] = useState(data.venue);
  const [organiser, setOrganiser] = useState(data.training_organiser);
  const [trainer, setTrainer] = useState(data.trainer);
  const [costAmount, setCostAmount] = useState(data.cost_amount);
  const [costCurrency, setCostCurrency] = useState(data.cost_currency);

  // Backend API Call Helper
  async function callBackend(endpoint) {
    const payload = {
      meta: {
        program_title: title,
        start_date: startDate,
        end_date: endDate,
        venue,
        training_organiser: organiser,
        trainer,
        cost_amount: costAmount,
        cost_currency: costCurrency,
        hrdc_certified: data.hrdc_certified,
        method: data.method,
        status: data.status,
      },
    };

    await fetch(`${API_BASE}${endpoint}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  }

  // Google Form 
  function handleApproveGoogle() {
    const baseUrl =
      "https://docs.google.com/forms/d/e/1FAIpQLSfqZezmVhQW8CDFAtGRPhDWIrVYTS1lBZLAW3oCQZ6_it9ehw/viewform";

    const params = new URLSearchParams({
      "entry.2068986276": title,
      "entry.485417362": startDate,
      "entry.2067817318": endDate,
      "entry.2139113983": venue,
      "entry.966550949": `${costCurrency}${costAmount}`,
      "entry.2087209596": trainer,
      "entry.1233652296": organiser,
      "entry.499212106": data.hrdc_certified,
      "entry.497656159": data.method,
    });

    window.open(`${baseUrl}?${params.toString()}`, "_blank");
    alert("Google Form opened with auto-filled data.");
  }

  // Backend Actions
  async function handleSaveDraft() {
    await callBackend("/draft");
    alert("Draft saved to backend");
  }

  function downloadUiVisionCSV() {
  const headers = ["ProgramTitle", "TrainingProvider", "Trainer", "HRDFund"];

  const hrdcValue =
    String(data.hrdc_certified).toLowerCase() === "yes" ||
    String(data.hrdc_certified).toLowerCase() === "true"
      ? "(Yes)"
      : "(No)";

  const values = [
    `"${title.replace(/"/g, '""')}"`,
    `"${organiser.replace(/"/g, '""')}"`,
    `"${trainer.replace(/"/g, '""')}"`,
    `"${hrdcValue}"`
  ];

  const csvContent = `${headers.join(",")}\n${values.join(",")}`;
  const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });

  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = "uivision_items.csv";
  link.click();
}

  return (
    <div className="review-card">
      <h2>Human Review</h2>

      <label>Program Title</label>
      <textarea
        className="long-input"
        value={title}
        onChange={(e) => setTitle(e.target.value)}
      />

      <label>Start Date</label>
      <input
        type="date"
        value={startDate}
        onChange={(e) => setStartDate(e.target.value)}
      />

      <label>End Date</label>
      <input
        type="date"
        value={endDate}
        onChange={(e) => setEndDate(e.target.value)}
      />

      <label>Venue</label>
      <textarea
        className="long-input"
        value={venue}
        onChange={(e) => setVenue(e.target.value)}
      />

      <label>Training Organiser</label>
      <textarea
        className="long-input"
        value={organiser}
        onChange={(e) => setOrganiser(e.target.value)}
      />

      <label>Trainer</label>
      <textarea
        className="long-input"
        value={trainer}
        onChange={(e) => setTrainer(e.target.value)}
      />

      <label>Cost</label>
      <div style={{ display: "flex", gap: "10px", marginTop: "6px" }}>
        <input
          type="text"
          placeholder="Currency"
          value={costCurrency}
          onChange={(e) => setCostCurrency(e.target.value)}
          style={{ flex: 1 }}
        />
        <input
          type="text"
          placeholder="Amount"
          value={costAmount}
          onChange={(e) => setCostAmount(e.target.value)}
          style={{ flex: 2 }}
        />
      </div>

      <p className={`status ${data.status === "READY_TO_FILL" ? "ready" : "review"}`}>
        Status: {data.status}
      </p>

      <h4>Confidence (AI)</h4>
      <ul className="confidence">
        <li>Title: {data.confidence_program_title}</li>
        <li>Date: {data.confidence_date}</li>
        <li>Venue: {data.confidence_venue}</li>
        <li>Cost: {data.confidence_cost}</li>
        <li>Trainer: {data.confidence_trainer}</li>
        <li>Organiser: {data.confidence_organiser}</li>
      </ul>

      <p><b>HRDC Certified:</b> {data.hrdc_certified}</p>
      <p><b>Extraction Method:</b> {data.method}</p>

      <div className="action-buttons">
        <button className="approve" onClick={handleApproveGoogle}>
          Approve & Send (Google Form)
        </button>

        <button className="draft" onClick={handleSaveDraft}>
          Save Draft
        </button>

        <button className="approve" onClick={downloadUiVisionCSV}>
          Download UI Vision CSV
        </button>

      </div>
    </div>
  );
}

// Main App
function App() {
  const [file, setFile] = useState(null);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  return (
    <div className="app">
      <h1>Training Brochure Extraction</h1>

      <div className="upload-card">
        <input
          type="file"
          accept="application/pdf"
          onChange={(e) => setFile(e.target.files[0])}
        />

        <button
          onClick={() => uploadFile(file, setResult, setLoading)}
          disabled={!file || loading}
        >
          {loading ? "Processing..." : "Upload & Extract"}
        </button>
      </div>

      {result && <ReviewForm data={result} />}
    </div>
  );
}

export default App;
