import React, { useEffect, useRef, useState } from "react";
import "./MedicineSafety.css";

function buildAlert(recognition, result, prescription) {
  const detections = recognition?.detections;
  if (!Array.isArray(detections)) return null;

  const threshold = Number.isFinite(result?.confidenceThreshold)
    ? result.confidenceThreshold
    : 0.65;

  const expected = new Map();

  if (
    result?.comparisonType === "product-count" &&
    Array.isArray(result.rows)
  ) {
    result.rows.forEach((row) => {
      if (
        row.productId &&
        Number.isInteger(row.expected) &&
        row.expected >= 0
      ) {
        expected.set(row.productId, row.expected);
      }
    });
  } else if (
    prescription?.reviewed === true &&
    Array.isArray(prescription.items)
  ) {
    prescription.items.forEach((item) => {
      if (
        item.productId &&
        Number.isInteger(item.quantity) &&
        item.quantity > 0
      ) {
        expected.set(
          item.productId,
          (expected.get(item.productId) || 0) + item.quantity
        );
      }
    });
  }

  const grouped = new Map();
  let uncertain = 0;

  detections.forEach((item) => {
    if (
      item.unmapped ||
      item.identityUncertain ||
      typeof item.confidence !== "number" ||
      !Number.isFinite(item.confidence) ||
      item.confidence < threshold ||
      !item.productId
    ) {
      uncertain += 1;
      return;
    }

    const current = grouped.get(item.productId) || {
      name: item.productName || item.label || item.productId,
      count: 0,
    };

    current.count += 1;
    grouped.set(item.productId, current);
  });

  const extra = [];
  const repeated = [];

  grouped.forEach((item, id) => {
    if (expected.has(id)) {
      const quantity = expected.get(id);
      if (item.count > quantity) {
        extra.push(
          `${item.name}: ${item.count} counted predictions; ` +
          `${quantity} expected in the reviewed list.`
        );
      }
    } else if (item.count > 1) {
      repeated.push(
        `${item.name}: the same label was predicted ` +
        `${item.count} times; no reviewed quantity is available.`
      );
    }
  });


  // COMPARISON_FLAGS_V2
  const comparisonDifferences = [];

  if (
    result?.comparisonType === "product-count" &&
    Array.isArray(result.rows)
  ) {
    result.rows.forEach((row) => {
      if (
        !Number.isInteger(row.expected) ||
        !Number.isInteger(row.found) ||
        row.expected === row.found
      ) {
        return;
      }

      const name =
        row.medicineName || row.productName || row.productId || "Medicine";

      if (row.expected === 0 && row.found > 0) {
        comparisonDifferences.push(
          `Unexpected predicted medicine: ${name}. ` +
          `${row.found} counted; none expected in the reviewed list.`
        );
      } else if (row.found < row.expected) {
        comparisonDifferences.push(
          `${name}: ${row.expected} expected, ${row.found} counted. ` +
          `One or more expected pills were not counted.`
        );
      } else {
        comparisonDifferences.push(
          `${name}: ${row.expected} expected, ${row.found} counted. ` +
          `More pills were predicted than expected.`
        );
      }
    });
  }

  if (
    result?.comparisonType === "total-count" &&
    Number.isInteger(result.expectedTotal) &&
    Number.isInteger(result.detectedTotal) &&
    result.expectedTotal !== result.detectedTotal
  ) {
    comparisonDifferences.push(
      `Total count difference: ${result.expectedTotal} expected, ` +
      `${result.detectedTotal} detected. Medicine identities were not checked.`
    );
  }

  const danger =
    comparisonDifferences.length > 0 || extra.length > 0;

  const details = [
    ...comparisonDifferences,
    ...(comparisonDifferences.length ? [] : extra),
    ...repeated,
  ];

  if (uncertain) {
    details.push(
      `${uncertain} detection(s) have an uncertain, unsupported ` +
      `or low-score identity. Check the original packaging.`
    );
  }

  if (!details.length) return null;

  return {
    tone: danger ? "danger" : "warning",
    title: danger
      ? "Comparison mismatch - check the tray"
      : repeated.length
      ? "Repeated predictions need a check"
      : "Medicine identity uncertain - check required",
    details,
  };
}


// REPEAT_AUDIO_FIX_V3

// NATIVE_MP3_PLAYER_V4
function createAlarmPlayer() {
  const recordings = new Map();
  let current = null;
  let timer = null;
  let generation = 0;

  function getAudio(filename) {
    if (!recordings.has(filename)) {
      const base = process.env.PUBLIC_URL || "";
      const audio = new Audio(`${base}/sounds/${filename}`);

      audio.preload = "auto";
      audio.loop = false;
      audio.volume = 0.85;
      audio.muted = false;

      recordings.set(filename, audio);
    }

    return recordings.get(filename);
  }

  function stop() {
    generation += 1;

    if (timer !== null) {
      window.clearTimeout(timer);
      timer = null;
    }

    if (current) {
      const previous = current;
      current = null;

      previous.ontimeupdate = null;
      previous.onended = null;
      previous.pause();

      try {
        previous.currentTime = 0;
      } catch {
        // Metadata may not have loaded yet.
      }
    }
  }

  async function unlock() {
    // Native media playback is attempted when the alert arrives.
    // The browser may still enforce its autoplay policy.
    return true;
  }

  async function preload() {
    getAudio("warning_msg.mp3");
    getAudio("alarm.mp3");
  }

  async function play(tone) {
    stop();
    const ticket = generation;

    const filename =
      tone === "danger" ? "warning_msg.mp3" : "alarm.mp3";
    const limit = tone === "danger" ? 1.1 : 2;
    const audio = getAudio(filename);

    // Retry loading if a previous request failed.
    if (audio.error) audio.load();

    current = audio;
    audio.muted = false;
    audio.volume = 0.85;
    audio.currentTime = 0;

    function finish() {
      if (ticket === generation && current === audio) {
        stop();
      }
    }

    audio.ontimeupdate = () => {
      if (audio.currentTime >= limit) finish();
    };
    audio.onended = finish;

    try {
      await audio.play();

      if (ticket !== generation || current !== audio) {
        return false;
      }

      timer = window.setTimeout(finish, limit * 1000);
      return true;
    } catch (error) {
      const code = audio.error?.code;
      const message =
        `${filename}: ${error?.name || "PlaybackError"} - ` +
        `${error?.message || "Playback failed"}` +
        (code ? `; media error code ${code}` : "");

      if (ticket === generation) stop();
      throw new Error(message);
    }
  }

  function dispose() {
    stop();
    recordings.forEach((audio) => {
      audio.pause();
      audio.removeAttribute("src");
      audio.load();
    });
    recordings.clear();
  }

  return { unlock, preload, play, stop, dispose };
}

export default function MedicineSafety({
  recognition,
  result,
  prescription,
}) {
  const [alert, setAlert] = useState(null);
  const [soundEnabled, setSoundEnabled] = useState(true);
  const [soundMessage, setSoundMessage] = useState("");

  const dialogRef = useRef(null);
  const soundEnabledRef = useRef(true);
  const mountedRef = useRef(false);
  const handledRef = useRef(null);
  const latestAlertRef = useRef(null);
  const alertSequenceRef = useRef(0);
  const playerRef = useRef(null);

  if (!playerRef.current) {
    playerRef.current = createAlarmPlayer();
  }

  const player = playerRef.current;

  useEffect(() => {
    mountedRef.current = true;
    let active = true;

    // Resume browser audio on each interaction, not just the first click.
    function prepareAudio() {
      if (!soundEnabledRef.current) return;

      player.preload().catch(() => {
        if (active) {
          setSoundMessage(
            "Browser audio is blocked. Visual alerts remain active."
          );
        }
      });
    }

    window.addEventListener("pointerdown", prepareAudio, true);
    window.addEventListener("keydown", prepareAudio, true);

    return () => {
      active = false;
      mountedRef.current = false;
      alertSequenceRef.current += 1;
      window.removeEventListener("pointerdown", prepareAudio, true);
      window.removeEventListener("keydown", prepareAudio, true);
      player.dispose();
    };
  }, [player]);

  useEffect(() => {
    // Fresh recognition responses are separate checks even when their
    // medicine labels and counts are identical.
    if (!recognition) {
      handledRef.current = null;
      latestAlertRef.current = null;
      alertSequenceRef.current += 1;
      player.stop();
      setAlert(null);
      return;
    }

    if (
      handledRef.current?.recognition === recognition &&
      handledRef.current?.result === result
    ) {
      return;
    }

    handledRef.current = { recognition, result };

    const next = buildAlert(recognition, result, prescription);
    const sequence = ++alertSequenceRef.current;

    latestAlertRef.current = next;
    player.stop();
    setAlert(next);

    if (!next || !soundEnabledRef.current) return;

    player.play(next.tone)
      .then((played) => {
        if (
          played &&
          mountedRef.current &&
          sequence === alertSequenceRef.current
        ) {
          setSoundMessage(
            next.tone === "danger"
              ? "1.1-second comparison warning played."
              : "Two-second review alarm played."
          );
        }
      })
      .catch((error) => {
        if (
          mountedRef.current &&
          sequence === alertSequenceRef.current
        ) {
          setSoundMessage(
            `Audio error: ${error?.message || "Playback failed"}`
          );
        }
      });
  }, [recognition, result, prescription, player]);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;

    if (alert && !dialog.open) {
      dialog.showModal();
    } else if (!alert && dialog.open) {
      dialog.close();
    }
  }, [alert]);

  async function toggleSound() {
    const enabled = !soundEnabledRef.current;

    soundEnabledRef.current = enabled;
    setSoundEnabled(enabled);

    if (!enabled) {
      player.stop();
      setSoundMessage("Alert sound muted.");
      return;
    }

    try {
      await player.unlock();

      if (!mountedRef.current || !soundEnabledRef.current) return;

      setSoundMessage("Alert sound is on.");

      const current = latestAlertRef.current;
      if (current) {
        await player.play(current.tone);
      }
    } catch {
      if (mountedRef.current) {
        setSoundMessage(
          "Sound is blocked. Visual alerts remain active."
        );
      }
    }
  }

  function dismiss() {
    latestAlertRef.current = null;
    alertSequenceRef.current += 1;
    player.stop();
    setAlert(null);
  }

  return (
    <>
      <section className="ms-intro ms-hero" aria-labelledby="ms-intro-title">
  {/* MEDICINE_HERO_V3 */}
  <div className="ms-hero-copy">
    <span className="ms-eyebrow">MEDICINE CARE, WITH CONFIDENCE IN THE PROCESS</span>
    <h2 id="ms-intro-title">
      A careful check.<br />
      Before every dose.
    </h2>
    <p>
      Review the prescription, check the prepared tray and investigate
      differences before administration. AI predictions support your review;
      they do not confirm medicine identity.
    </p>

    <div className="ms-hero-steps" aria-label="Care workflow">
      <span><b>01</b> Read</span>
      <span><b>02</b> Review</span>
      <span><b>03</b> Check tray</span>
    </div>

    <div className="ms-hero-controls">

      <button
        type="button"
        className="ms-sound-control"
        aria-pressed={soundEnabled}
        onClick={toggleSound}
      >
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path
            d="m11 5-5 4H3v6h3l5 4V5Z"
            stroke="currentColor"
            strokeWidth="1.7"
            strokeLinejoin="round"
          />
          {soundEnabled ? (
            <path
              d="M15 8a6 6 0 0 1 0 8m3-11a10 10 0 0 1 0 14"
              stroke="currentColor"
              strokeWidth="1.7"
              strokeLinecap="round"
            />
          ) : (
            <path
              d="m16 9 5 6m0-6-5 6"
              stroke="currentColor"
              strokeWidth="1.7"
              strokeLinecap="round"
            />
          )}
        </svg>
        {soundEnabled ? "Sound on - mute" : "Sound off - unmute"}
      </button>
      <span className="ms-hero-reminder">Manual review remains essential</span>
      <span className="av-sr" role="status">{soundMessage}</span>
    </div>
  </div>

  <div className="ms-hero-art ms-hero-photo">
    <img
      src={`${process.env.PUBLIC_URL || ""}/images/medicine-care.png`}
      alt="Illustrative caregiver reviewing a blister pack beside a medicine organiser"
      width="1448"
      height="1086"
      decoding="async"
    />
    <span>Careful preparation. Thoughtful review.</span>
  </div>
</section>


      {recognition && (() => {
        const status = buildAlert(recognition, result, prescription);
        if (!status) return null;

        return (
          <div
            className={`ms-result-flag ${status.tone}`}
            role="status"
          >
            <span className="ms-result-flag-icon" aria-hidden="true">!</span>
            <div>
              <strong>{status.title}</strong>
              <p>
                {status.tone === "danger"
                  ? "The predicted contents do not match the reviewed list. Check the medicines and quantities."
                  : "Some predictions need a manual check against the reviewed list and packaging."}
              </p>
            </div>
          </div>
        );
      })()}

      <dialog
        ref={dialogRef}
        className={`ms-dialog ${alert?.tone || "warning"}`}
        aria-labelledby="ms-dialog-title"
        aria-describedby="ms-dialog-description"
        onCancel={dismiss}
      >
        <div className="ms-dialog-heading">
          <span className="ms-dialog-symbol" aria-hidden="true">
            <svg
              className="ms-warning-triangle"
              viewBox="0 0 100 92"
              fill="none"
            >
              <path
                d="M45.6 8.6a5.1 5.1 0 0 1 8.8 0l39 67.6a5.1 5.1 0 0 1-4.4 7.6H11a5.1 5.1 0 0 1-4.4-7.6l39-67.6Z"
                fill={alert?.tone === "danger" ? "#ffffff" : "#ffdf18"}
                stroke={alert?.tone === "danger" ? "#d71920" : "#20251f"}
                strokeWidth="7"
                strokeLinejoin="round"
              />
              <path
                d="M50 31v25"
                stroke="#171b17"
                strokeWidth="8"
                strokeLinecap="round"
              />
              <circle cx="50" cy="69" r="4.5" fill="#171b17" />
            </svg>
          </span>
          <div>
            <span className="ms-eyebrow">TRAY REVIEW ALERT</span>
            <h2 id="ms-dialog-title">{alert?.title || "Review the tray"}</h2>
          </div>
        </div>

        <p id="ms-dialog-description">
          Compare the tray with the reviewed prescription and original
          packaging before proceeding.
        </p>

        <ul className="ms-alert-list">
          {(alert?.details || []).map((detail, index) => (
            <li key={index}>{detail}</li>
          ))}
        </ul>

        <p className="ms-disclaimer">
          Repeated labels are model predictions, not confirmed duplicate
          medicines. A prescribed quantity of two or more tablets can be valid.
          This alert does not recommend a dose change.
        </p>

        <div className="ms-dialog-actions">
          {soundEnabled && (
            <button
              type="button"
              className="av-button"
              onClick={toggleSound}
            >
              Mute sound
            </button>
          )}
          <button
            type="button"
            className="av-button av-primary"
            autoFocus
            onClick={dismiss}
          >
            Close and review results
          </button>
        </div>
      </dialog>
    </>
  );
}
