import { useState } from "react";
import axios from "axios";
import "./App.css";

function App() {
  const [text, setText] = useState<string>();
  const [result, setResult] = useState<string[]>([]);
  const [loading, toggleLoading] = useState<boolean>(false);
  const [error, setError] = useState<string>();

  const askAI = async () => {
    toggleLoading((prev) => !prev);
    try {
      const result = await axios.post(
        "http://127.0.0.1:8000/monitoring-assistant",
        { text: text }
      );
      setResult(result.data.message);
    } catch (error) {
      setError("Error occur");
    }

    toggleLoading((prev) => !prev);
  };

  return (
    <>
      <div>
        <h3>What do you want to know about your system today?</h3>
        <textarea
          name=""
          id=""
          cols="80"
          rows="10"
          onChange={(event) => setText(event.target.value)}
        ></textarea>
        {loading && <h1>Request is sending</h1>}
        {error && <h3>{error}</h3>}
        <div>
          <button onClick={askAI}>ASK</button>
        </div>
        <div className="display-result">{result}</div>
      </div>
    </>
  );
}

export default App;
