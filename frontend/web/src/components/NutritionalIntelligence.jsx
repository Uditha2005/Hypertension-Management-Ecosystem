import React, { useEffect, useRef, useState } from "react";

const acceptedTypes = "image/jpeg,image/png,image/webp";

const detectedFoods = [
  { name: "Grilled Chicken", portion: "120 g", color: "#e56b5d", top: "18%", left: "12%", width: "35%", height: "38%" },
  { name: "Steamed Rice", portion: "180 g", color: "#e0a12f", top: "36%", left: "52%", width: "37%", height: "34%" },
  { name: "Salad", portion: "95 g", color: "#3c9b70", top: "10%", left: "58%", width: "27%", height: "22%" },
];

function NutritionalIntelligence() {
  const [previewUrl, setPreviewUrl] = useState("");
  const [fileName, setFileName] = useState("");
  const [isDragging, setIsDragging] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [status, setStatus] = useState("Add a clear photo of your meal to begin");
  const [analysis, setAnalysis] = useState(null);
  const fileInputRef = useRef(null);

  useEffect(() => {
    return () => {
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl);
      }
    };
  }, [previewUrl]);

  const useImage = (file) => {
    if (!file || !file.type.startsWith("image/")) {
      setStatus("Please choose a JPG, PNG, or WebP image");
      return;
    }

    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
    }

    setPreviewUrl(URL.createObjectURL(file));
    setFileName(file.name);
    setAnalysis(null);
    setStatus("Meal photo ready to analyze");
  };

  const handleFileChange = (event) => {
    useImage(event.target.files[0]);
    event.target.value = "";
  };

  const handleDrop = (event) => {
    event.preventDefault();
    setIsDragging(false);
    useImage(event.dataTransfer.files[0]);
  };

  const analyzeMeal = () => {
    if (!previewUrl) {
      setStatus("Upload a meal photo before analyzing");
      fileInputRef.current?.focus();
      return;
    }

    setIsAnalyzing(true);
    setStatus("Analyzing meal...");

    window.setTimeout(() => {
      setAnalysis({
        calories: "520 kcal",
        protein: "28 g",
        carbs: "48 g",
        fats: "18 g",
        sodium: "610 mg",
        sugar: "9 g",
      });
      setIsAnalyzing(false);
      setStatus("Meal analysis complete");
    }, 700);
  };

  return (
    <main className="nutritional-intelligence">
      <style>{`
        .nutritional-intelligence {
          --ink: #18342f;
          --muted: #667a75;
          --line: #d7e5df;
          --canvas: #f4f8f3;
          --leaf: #28745b;
          --leaf-dark: #1d5744;
          --sun: #f0b55c;
          min-height: 100vh;
          padding: clamp(24px, 5vw, 72px);
          color: var(--ink);
          background: linear-gradient(135deg, #eef7ef 0%, var(--canvas) 52%, #fff7e8 100%);
          font-family: Georgia, "Times New Roman", serif;
        }
        .nutritional-intelligence * { box-sizing: border-box; }
        .nutrition-shell { max-width: 980px; margin: 0 auto; }
        .nutrition-kicker {
          margin: 0 0 10px;
          color: var(--leaf);
          font: 700 0.72rem/1.2 Arial, sans-serif;
          letter-spacing: 0.14em;
          text-transform: uppercase;
        }
        .nutrition-title { max-width: 650px; margin: 0; font-size: clamp(2.3rem, 6vw, 4.5rem); line-height: 0.98; }
        .nutrition-intro { max-width: 570px; margin: 18px 0 34px; color: var(--muted); font: 1rem/1.6 Arial, sans-serif; }
        .nutrition-grid { display: grid; grid-template-columns: minmax(0, 1.2fr) minmax(280px, 0.8fr); gap: 22px; align-items: start; }
        .upload-panel, .results-panel { border: 1px solid var(--line); background: rgba(255, 255, 255, 0.82); box-shadow: 0 16px 40px rgba(40, 78, 62, 0.08); }
        .upload-panel { padding: clamp(20px, 4vw, 38px); }
        .drop-zone {
          min-height: 340px;
          display: grid;
          place-items: center;
          padding: 24px;
          border: 1.5px dashed #8ab5a0;
          background: #f8fcf8;
          text-align: center;
          transition: border-color 160ms ease, background 160ms ease;
        }
        .drop-zone.dragging, .drop-zone:hover { border-color: var(--leaf); background: #eef8f0; }
        .preview-stage { position: relative; width: 100%; height: 290px; overflow: hidden; background: #dfeae1; }
        .preview { width: 100%; height: 100%; object-fit: cover; display: block; }
        .food-box { position: absolute; border: 2px solid var(--box-color); background: color-mix(in srgb, var(--box-color) 12%, transparent); pointer-events: none; }
        .food-label { position: absolute; top: -2px; left: -2px; max-width: 100%; padding: 5px 7px; color: #fff; background: var(--box-color); font: 700 0.68rem/1.1 Arial, sans-serif; white-space: nowrap; }
        .food-portion { display: block; margin-top: 2px; font-weight: 400; opacity: 0.9; }
        .detection-legend { display: flex; flex-wrap: wrap; gap: 8px 14px; margin: 12px 0 0; color: var(--muted); font: 0.72rem Arial, sans-serif; }
        .legend-item { display: inline-flex; align-items: center; gap: 5px; }
        .legend-dot { width: 8px; height: 8px; background: var(--dot-color); }
        .upload-mark { width: 58px; height: 58px; display: grid; place-items: center; margin: 0 auto 16px; border-radius: 50%; color: var(--leaf-dark); background: #dcefe1; font: 700 1.8rem/1 Arial, sans-serif; }
        .drop-title { margin: 0; font-size: 1.45rem; }
        .drop-copy { margin: 9px 0 18px; color: var(--muted); font: 0.86rem/1.5 Arial, sans-serif; }
        .choose-button, .analyze-button { border: 0; cursor: pointer; font: 700 0.83rem Arial, sans-serif; }
        .choose-button { padding: 12px 18px; color: #fff; background: var(--leaf); }
        .choose-button:hover { background: var(--leaf-dark); }
        .file-name { margin: 14px 0 0; overflow: hidden; color: var(--muted); font: 0.78rem Arial, sans-serif; text-overflow: ellipsis; white-space: nowrap; }
        .upload-actions { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-top: 20px; }
        .status { margin: 0; color: var(--muted); font: 0.8rem/1.4 Arial, sans-serif; }
        .analyze-button { min-height: 46px; padding: 0 22px; color: #fff; background: var(--leaf-dark); }
        .analyze-button:hover:not(:disabled) { background: #143e31; }
        .analyze-button:disabled { cursor: wait; opacity: 0.55; }
        .results-panel { padding: 26px; }
        .results-label { margin: 0 0 8px; color: var(--leaf); font: 700 0.7rem Arial, sans-serif; letter-spacing: 0.12em; text-transform: uppercase; }
        .results-title { margin: 0 0 22px; font-size: 1.7rem; }
        .empty-results { margin: 0; color: var(--muted); font: 0.9rem/1.55 Arial, sans-serif; }
        .calorie-total { margin: 0 0 24px; padding-bottom: 20px; border-bottom: 1px solid var(--line); }
        .calorie-value { display: block; margin-top: 3px; color: var(--leaf-dark); font-size: 2.55rem; line-height: 1; }
        .calorie-caption { display: block; margin-top: 7px; color: var(--muted); font: 0.78rem Arial, sans-serif; }
        .macro-list { display: grid; gap: 17px; margin: 0; }
        .macro-heading { display: flex; justify-content: space-between; gap: 12px; margin-bottom: 7px; font: 700 0.82rem Arial, sans-serif; }
        .macro-heading span:last-child { color: var(--leaf-dark); }
        .macro-track { height: 8px; overflow: hidden; background: #e6eee8; }
        .macro-bar { height: 100%; background: var(--macro-color); transition: width 300ms ease; }
        .sodium-note { margin: 22px 0 0; padding: 13px; border-left: 3px solid var(--sun); color: #6a522e; background: #fff7e8; font: 0.78rem/1.45 Arial, sans-serif; }
        .insight-grid { display: grid; grid-template-columns: 1.15fr 0.85fr; gap: 22px; margin-top: 22px; }
        .insight-section { padding: 26px; border: 1px solid var(--line); background: rgba(255, 255, 255, 0.82); box-shadow: 0 16px 40px rgba(40, 78, 62, 0.08); }
        .insight-heading { margin: 0 0 7px; font-size: 1.45rem; }
        .insight-copy { margin: 0 0 20px; color: var(--muted); font: 0.82rem/1.5 Arial, sans-serif; }
        .profile-strip { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 20px; }
        .profile-item { padding: 8px 10px; color: var(--leaf-dark); background: #eaf4ec; font: 700 0.72rem Arial, sans-serif; }
        .recommendation-list { display: grid; gap: 12px; margin: 0; padding: 0; list-style: none; }
        .recommendation-item { display: grid; grid-template-columns: 24px 1fr; gap: 10px; align-items: start; font: 0.83rem/1.45 Arial, sans-serif; }
        .recommendation-icon { display: grid; place-items: center; width: 24px; height: 24px; color: #fff; background: var(--leaf); font-size: 0.75rem; }
        .behavior-panel { border-color: #e9d6b7; background: #fffaf0; }
        .warning-title { display: flex; gap: 9px; align-items: center; margin: 0 0 12px; color: #855c24; font-size: 1.45rem; }
        .warning-icon { display: grid; place-items: center; width: 27px; height: 27px; color: #fff; background: var(--sun); font: 700 0.9rem Arial, sans-serif; }
        .trend-list { display: grid; gap: 14px; margin: 0; padding: 0; list-style: none; }
        .trend-item { padding-bottom: 13px; border-bottom: 1px solid #eddcbe; font: 0.8rem/1.45 Arial, sans-serif; }
        .trend-item:last-child { padding-bottom: 0; border-bottom: 0; }
        .trend-label { display: block; margin-bottom: 3px; color: #855c24; font-weight: 700; }
        .trend-detail { color: #735f43; }
        @media (max-width: 720px) {
          .nutrition-grid { grid-template-columns: 1fr; }
          .insight-grid { grid-template-columns: 1fr; }
          .drop-zone { min-height: 280px; }
          .upload-actions { align-items: stretch; flex-direction: column; }
          .analyze-button { width: 100%; }
        }
      `}</style>

      <section className="nutrition-shell" aria-labelledby="nutrition-title">
        <p className="nutrition-kicker">Nutrition intelligence</p>
        <h1 className="nutrition-title" id="nutrition-title">See what is on your plate.</h1>
        <p className="nutrition-intro">Upload a meal photo to receive a quick nutrition snapshot that can support healthier blood-pressure choices.</p>

        <div className="nutrition-grid">
          <section className="upload-panel" aria-label="Meal image upload">
            <div
              className={`drop-zone${isDragging ? " dragging" : ""}`}
              onDragEnter={(event) => { event.preventDefault(); setIsDragging(true); }}
              onDragOver={(event) => event.preventDefault()}
              onDragLeave={(event) => { if (event.currentTarget === event.target) setIsDragging(false); }}
              onDrop={handleDrop}
            >
              {previewUrl ? (
                <div className="preview-stage">
                  <img className="preview" src={previewUrl} alt={`Selected meal: ${fileName}`} />
                  {detectedFoods.map((food) => (
                    <div
                      className="food-box"
                      key={food.name}
                      style={{
                        "--box-color": food.color,
                        top: food.top,
                        left: food.left,
                        width: food.width,
                        height: food.height,
                      }}
                    >
                      <span className="food-label">
                        {food.name}
                        <span className="food-portion">{food.portion}</span>
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <div>
                  <div className="upload-mark" aria-hidden="true">+</div>
                  <h2 className="drop-title">Drop your meal photo here</h2>
                  <p className="drop-copy">JPG, PNG, or WebP up to 10 MB</p>
                  <button className="choose-button" type="button" onClick={() => fileInputRef.current?.click()}>
                    Choose image
                  </button>
                </div>
              )}
            </div>
            <input ref={fileInputRef} type="file" accept={acceptedTypes} onChange={handleFileChange} hidden />
            {fileName && <p className="file-name" title={fileName}>{fileName}</p>}
            {previewUrl && (
              <div className="detection-legend" aria-label="Detected food items">
                {detectedFoods.map((food) => (
                  <span className="legend-item" key={food.name}>
                    <span className="legend-dot" style={{ "--dot-color": food.color }} aria-hidden="true" />
                    {food.name}: {food.portion}
                  </span>
                ))}
              </div>
            )}
            <div className="upload-actions">
              <p className="status" role="status">{status}</p>
              <button className="analyze-button" type="button" onClick={analyzeMeal} disabled={isAnalyzing}>
                {isAnalyzing ? "Analyzing..." : "Analyze Meal"}
              </button>
            </div>
          </section>

          <aside className="results-panel" aria-live="polite">
            <p className="results-label">Meal snapshot</p>
            <h2 className="results-title">Nutrition at a glance</h2>
            {analysis ? (
              <>
                <div className="calorie-total">
                  <span className="calorie-value">{analysis.calories}</span>
                  <span className="calorie-caption">Total estimated calories</span>
                </div>
                <dl className="macro-list">
                  {[
                    { label: "Protein", value: analysis.protein, progress: "56%", color: "#3c9b70" },
                    { label: "Carbs", value: analysis.carbs, progress: "68%", color: "#e0a12f" },
                    { label: "Fats", value: analysis.fats, progress: "42%", color: "#e56b5d" },
                    { label: "Sodium", value: analysis.sodium, progress: "61%", color: "#7c78b8" },
                    { label: "Sugar", value: analysis.sugar, progress: "24%", color: "#c67c9a" },
                  ].map((macro) => (
                    <div key={macro.label}>
                      <div className="macro-heading"><span>{macro.label}</span><span>{macro.value}</span></div>
                      <div className="macro-track" aria-label={`${macro.label}: ${macro.value}`}>
                        <div className="macro-bar" style={{ "--macro-color": macro.color, width: macro.progress }} />
                      </div>
                    </div>
                  ))}
                </dl>
                <p className="sodium-note">Sodium is highlighted because keeping an eye on salt intake can support blood-pressure management.</p>
              </>
            ) : (
              <p className="empty-results">Your meal breakdown will appear here after you upload an image and analyze it.</p>
            )}
          </aside>
        </div>

        <div className="insight-grid">
          <section className="insight-section" aria-labelledby="recommendations-title">
            <p className="results-label">Personalized guidance</p>
            <h2 className="insight-heading" id="recommendations-title">Recommendations for your health profile</h2>
            <p className="insight-copy">Suggestions are based on your recorded BMI and hypertension profile.</p>
            <div className="profile-strip" aria-label="Health profile summary">
              <span className="profile-item">BMI 27.4</span>
              <span className="profile-item">Hypertension stage 1</span>
              <span className="profile-item">Sodium goal &lt; 1,500 mg</span>
            </div>
            <ul className="recommendation-list">
              <li className="recommendation-item"><span className="recommendation-icon" aria-hidden="true">1</span><span>Choose grilled or steamed proteins more often to support gradual weight reduction.</span></li>
              <li className="recommendation-item"><span className="recommendation-icon" aria-hidden="true">2</span><span>Add another serving of leafy vegetables and keep half your plate produce.</span></li>
              <li className="recommendation-item"><span className="recommendation-icon" aria-hidden="true">3</span><span>Swap salty sauces for herbs, citrus, or low-sodium alternatives.</span></li>
            </ul>
          </section>

          <section className="insight-section behavior-panel" aria-labelledby="behavior-title">
            <p className="results-label">Behavior watch</p>
            <h2 className="warning-title" id="behavior-title"><span className="warning-icon" aria-hidden="true">!</span>Eating pattern alert</h2>
            <p className="insight-copy">Recent meal history suggests a few patterns worth noticing early.</p>
            <ul className="trend-list">
              <li className="trend-item"><span className="trend-label">Overeating pattern</span><span className="trend-detail">3 meals this week were above your estimated calorie target.</span></li>
              <li className="trend-item"><span className="trend-label">Fast-food dependency</span><span className="trend-detail">Fast food appeared 4 times in the last 7 days, often at dinner.</span></li>
              <li className="trend-item"><span className="trend-label">Next small step</span><span className="trend-detail">Plan one quick home-cooked dinner before your busiest evening.</span></li>
            </ul>
          </section>
        </div>
      </section>
    </main>
  );
}

export default NutritionalIntelligence;
