
import React, { useCallback, useEffect, useMemo, useState } from "react";

const API_URL = "http://localhost:5000/api/behavioral/fall-events";

const styles = {
  page: {
    padding: "28px",
    maxWidth: "1400px",
    margin: "0 auto",
    color: "#172033",
    fontFamily: "inherit",
  },
  heading: {
    fontSize: "28px",
    fontWeight: 700,
    margin: "0 0 8px",
  },
  subtitle: {
    color: "#64748b",
    margin: "0 0 24px",
    lineHeight: 1.5,
  },
  summaryGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))",
    gap: "16px",
    marginBottom: "24px",
  },
  card: {
    background: "#fff",
    border: "1px solid #e2e8f0",
    borderRadius: "12px",
    padding: "20px",
    boxShadow: "0 2px 8px rgba(15, 23, 42, 0.04)",
  },
  metricLabel: {
    fontSize: "13px",
    color: "#64748b",
    marginBottom: "8px",
  },
  metricValue: {
    fontSize: "28px",
    fontWeight: 700,
    color: "#172033",
  },
  filterGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
    gap: "16px",
    alignItems: "end",
  },
  label: {
    display: "block",
    fontSize: "13px",
    fontWeight: 600,
    marginBottom: "7px",
    color: "#334155",
  },
  input: {
    boxSizing: "border-box",
    width: "100%",
    minHeight: "42px",
    padding: "9px 11px",
    border: "1px solid #cbd5e1",
    borderRadius: "8px",
    background: "#fff",
    color: "#172033",
    fontSize: "14px",
  },
  button: {
    minHeight: "42px",
    padding: "10px 16px",
    background: "#172554",
    color: "#fff",
    border: "none",
    borderRadius: "8px",
    fontWeight: 600,
    cursor: "pointer",
  },
  secondaryButton: {
    minHeight: "42px",
    padding: "10px 16px",
    background: "#fff",
    color: "#172554",
    border: "1px solid #cbd5e1",
    borderRadius: "8px",
    fontWeight: 600,
    cursor: "pointer",
  },
  tableWrap: {
    overflowX: "auto",
    width: "100%",
  },
  table: {
    width: "100%",
    borderCollapse: "collapse",
    fontSize: "13px",
    minWidth: "850px",
  },
  th: {
    textAlign: "left",
    padding: "13px 14px",
    background: "#f8fafc",
    color: "#475569",
    borderBottom: "1px solid #e2e8f0",
    whiteSpace: "nowrap",
  },
  td: {
    padding: "14px",
    borderBottom: "1px solid #edf2f7",
    verticalAlign: "top",
  },
  error: {
    padding: "14px",
    marginBottom: "16px",
    background: "#fef2f2",
    border: "1px solid #fecaca",
    color: "#991b1b",
    borderRadius: "8px",
  },
  empty: {
    textAlign: "center",
    padding: "36px 16px",
    color: "#64748b",
  },
  searchInput: {
    boxSizing: "border-box",
    width: "100%",
    minHeight: "42px",
    padding: "9px 11px",
    border: "1px solid #cbd5e1",
    borderRadius: "8px",
    background: "#fff",
    color: "#172033",
    fontSize: "14px",
  },
  paginationButton: {
    minHeight: "36px",
    minWidth: "38px",
    padding: "7px 11px",
    background: "#fff",
    color: "#172554",
    border: "1px solid #cbd5e1",
    borderRadius: "7px",
    fontWeight: 600,
    cursor: "pointer",
  },
  paginationButtonActive: {
    minHeight: "36px",
    minWidth: "38px",
    padding: "7px 11px",
    background: "#172554",
    color: "#fff",
    border: "1px solid #172554",
    borderRadius: "7px",
    fontWeight: 600,
    cursor: "pointer",
  },
};

function formatDateTime(value) {
  if (!value) return "—";

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) return "—";

  return date.toLocaleString();
}

function formatProbability(value) {
  if (value === null || value === undefined || value === "") {
    return "—";
  }

  const number = Number(value);

  if (!Number.isFinite(number)) return "—";

  return `${(number * 100).toFixed(1)}%`;
}

function formatVideoTime(value) {
  if (value === null || value === undefined || value === "") {
    return "—";
  }

  const seconds = Number(value);

  if (!Number.isFinite(seconds) || seconds < 0) return "—";

  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = (seconds % 60).toFixed(1);

  return `${String(minutes).padStart(2, "0")}:${String(
    remainingSeconds
  ).padStart(4, "0")}`;
}

function getSourceLabel(source) {
  if (source === "uploaded_video") return "By Video";
  if (source === "live_camera") return "Live Camera";
  return source || "Unknown";
}

export default function NotificationHistory() {
  const [events, setEvents] = useState([]);
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const [source, setSource] = useState("all");
  const [searchTerm, setSearchTerm] = useState("");
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [lastUpdated, setLastUpdated] = useState(null);

  const loadEvents = useCallback(async () => {
    setLoading(true);
    setError("");

    try {
      const params = new URLSearchParams();

      if (fromDate) params.set("from", fromDate);
      if (toDate) params.set("to", toDate);
      if (source !== "all") params.set("source", source);

      const query = params.toString();
      const url = query ? `${API_URL}?${query}` : API_URL;

      const response = await fetch(url);

      if (!response.ok) {
        throw new Error(`Unable to load history (HTTP ${response.status}).`);
      }

      const data = await response.json();

      setEvents(Array.isArray(data.events) ? data.events : []);
      setLastUpdated(new Date());
    } catch (err) {
      setError(
        `${err.message} Check that the Node.js backend is running on port 5000.`
      );
    } finally {
      setLoading(false);
    }
  }, [fromDate, toDate, source]);

  useEffect(() => {
    loadEvents();
  }, [loadEvents]);

  const filteredEvents = useMemo(() => {
    const term = searchTerm.trim().toLowerCase();

    if (!term) return events;

    return events.filter((event) => {
      const searchableValues = [
        event.residentName,
        event.residentId,
        event.trackId,
        event.source,
        getSourceLabel(event.source),
      ];

      return searchableValues.some((value) =>
        String(value ?? "").toLowerCase().includes(term)
      );
    });
  }, [events, searchTerm]);

  const totalPages = Math.max(1, Math.ceil(filteredEvents.length / pageSize));

  const paginatedEvents = useMemo(() => {
    const startIndex = (currentPage - 1) * pageSize;
    return filteredEvents.slice(startIndex, startIndex + pageSize);
  }, [filteredEvents, currentPage, pageSize]);

  useEffect(() => {
    setCurrentPage(1);
  }, [searchTerm, fromDate, toDate, source, pageSize]);

  useEffect(() => {
    if (currentPage > totalPages) {
      setCurrentPage(totalPages);
    }
  }, [currentPage, totalPages]);

  const clearFilters = () => {
    setFromDate("");
    setToDate("");
    setSource("all");
    setSearchTerm("");
    setCurrentPage(1);
  };

  const videoCount = filteredEvents.filter(
    (event) => event.source === "uploaded_video"
  ).length;

  const liveCount = filteredEvents.filter(
    (event) => event.source === "live_camera"
  ).length;

  return (
    <div style={styles.page}>
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          alignItems: "flex-start",
          justifyContent: "space-between",
          gap: "16px",
          marginBottom: "8px",
        }}
      >
        <div>
          <h1 style={styles.heading}>Notification History</h1>
          <p style={styles.subtitle}>
            Review detected fall events from uploaded videos and live camera
            monitoring.
          </p>
        </div>

        <button
          type="button"
          style={styles.button}
          onClick={loadEvents}
          disabled={loading}
        >
          {loading ? "Loading..." : "Refresh"}
        </button>
      </div>

      <div style={styles.summaryGrid}>
        <div style={styles.card}>
          <div style={styles.metricLabel}>Total Events</div>
          <div style={styles.metricValue}>
            {loading ? "—" : events.length}
          </div>
        </div>

        <div style={styles.card}>
          <div style={styles.metricLabel}>By Video</div>
          <div style={styles.metricValue}>{loading ? "—" : videoCount}</div>
        </div>

        <div style={styles.card}>
          <div style={styles.metricLabel}>Live Camera</div>
          <div style={styles.metricValue}>{loading ? "—" : liveCount}</div>
        </div>
      </div>

      <section style={{ ...styles.card, marginBottom: "24px" }}>
        <h2 style={{ fontSize: "18px", margin: "0 0 18px" }}>
          Filter Notifications
        </h2>

        <div style={styles.filterGrid}>
          <div>
            <label style={styles.label} htmlFor="history-from-date">
              From Date
            </label>
            <input
              id="history-from-date"
              type="date"
              style={styles.input}
              value={fromDate}
              max={toDate || undefined}
              onChange={(event) => setFromDate(event.target.value)}
            />
          </div>

          <div>
            <label style={styles.label} htmlFor="history-to-date">
              To Date
            </label>
            <input
              id="history-to-date"
              type="date"
              style={styles.input}
              value={toDate}
              min={fromDate || undefined}
              onChange={(event) => setToDate(event.target.value)}
            />
          </div>

          <div>
            <label style={styles.label} htmlFor="history-source">
              Detection Source
            </label>
            <select
              id="history-source"
              style={styles.input}
              value={source}
              onChange={(event) => setSource(event.target.value)}
            >
              <option value="all">All Sources</option>
              <option value="uploaded_video">By Video</option>
              <option value="live_camera">Live Camera</option>
            </select>
          </div>

          <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
            <button
              type="button"
              style={styles.button}
              onClick={loadEvents}
              disabled={loading}
            >
              Apply Filters
            </button>

            <button
              type="button"
              style={styles.secondaryButton}
              onClick={clearFilters}
            >
              Clear
            </button>
          </div>
        </div>
      </section>

      <section style={styles.card}>
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            alignItems: "center",
            justifyContent: "space-between",
            gap: "12px",
            marginBottom: "16px",
          }}
        >
          <h2 style={{ fontSize: "18px", margin: 0 }}>Fall Events</h2>

          <span style={{ fontSize: "13px", color: "#64748b" }}>
            {loading
              ? "Loading events..."
              : `${filteredEvents.length} event(s)`}
          </span>
        </div>

        {error && <div style={styles.error}>{error}</div>}

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
            gap: "14px",
            marginBottom: "18px",
          }}
        >
          <div>
            <label style={styles.label} htmlFor="history-search">
              Search Resident / ID / Track ID
            </label>
            <input
              id="history-search"
              type="search"
              style={styles.searchInput}
              placeholder="Enter name, resident ID or track ID..."
              value={searchTerm}
              onChange={(event) => setSearchTerm(event.target.value)}
            />
          </div>

          <div style={{ maxWidth: "220px" }}>
            <label style={styles.label} htmlFor="history-page-size">
              Rows per page
            </label>
            <select
              id="history-page-size"
              style={styles.input}
              value={pageSize}
              onChange={(event) => setPageSize(Number(event.target.value))}
            >
              <option value={5}>5 per page</option>
              <option value={10}>10 per page</option>
              <option value={20}>20 per page</option>
              <option value={50}>50 per page</option>
            </select>
          </div>
        </div>

        {!error && !loading && filteredEvents.length === 0 && (
          <div style={styles.empty}>
            <div style={{ fontSize: "17px", fontWeight: 600 }}>
              No notifications found
            </div>
            <p style={{ marginBottom: 0 }}>
              Try changing the date or source filters, or check again after a
              fall event has been recorded.
            </p>
          </div>
        )}

        {loading && (
          <div style={styles.empty}>Loading notification history...</div>
        )}

        {!loading && filteredEvents.length > 0 && (
          <div style={styles.tableWrap}>
            <table style={styles.table}>
              <thead>
                <tr>
                  <th style={styles.th}>Date &amp; Time</th>
                  <th style={styles.th}>Resident</th>
                  <th style={styles.th}>Resident ID</th>
                  <th style={styles.th}>Source</th>
                  <th style={styles.th}>Probability</th>
                  <th style={styles.th}>Video Time</th>
                  <th style={styles.th}>Track ID</th>
                </tr>
              </thead>

              <tbody>
                {paginatedEvents.map((event) => (
                  <tr key={event.id}>
                    <td style={styles.td}>
                      {formatDateTime(event.occurredAt)}
                    </td>

                    <td style={styles.td}>
                      {event.residentName || "Unknown Resident"}
                    </td>

                    <td style={styles.td}>{event.residentId || "—"}</td>

                    <td style={styles.td}>
                      <span
                        style={{
                          display: "inline-block",
                          padding: "5px 9px",
                          borderRadius: "6px",
                          fontWeight: 600,
                          fontSize: "12px",
                          whiteSpace: "nowrap",
                          color:
                            event.source === "live_camera"
                              ? "#1d4ed8"
                              : "#475569",
                          background:
                            event.source === "live_camera"
                              ? "#dbeafe"
                              : "#f1f5f9",
                        }}
                      >
                        {getSourceLabel(event.source)}
                      </span>
                    </td>

                    <td style={styles.td}>
                      {formatProbability(event.probability)}
                    </td>

                    <td style={styles.td}>
                      {event.source === "uploaded_video"
                        ? formatVideoTime(event.videoTimeSeconds)
                        : "—"}
                    </td>

                    <td style={styles.td}>{event.trackId ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {!loading && !error && filteredEvents.length > 0 && (
          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              alignItems: "center",
              justifyContent: "space-between",
              gap: "12px",
              marginTop: "18px",
            }}
          >
            <span style={{ fontSize: "13px", color: "#64748b" }}>
              Showing {(currentPage - 1) * pageSize + 1}–
              {Math.min(currentPage * pageSize, filteredEvents.length)} of{" "}
              {filteredEvents.length} event(s)
            </span>

            <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
              <button
                type="button"
                style={styles.paginationButton}
                onClick={() => setCurrentPage(1)}
                disabled={currentPage === 1}
                aria-label="First page"
              >
                «
              </button>

              <button
                type="button"
                style={styles.paginationButton}
                onClick={() => setCurrentPage((page) => Math.max(1, page - 1))}
                disabled={currentPage === 1}
              >
                Previous
              </button>

              <span
                style={{
                  minWidth: "90px",
                  textAlign: "center",
                  fontSize: "13px",
                  color: "#475569",
                }}
              >
                Page {currentPage} of {totalPages}
              </span>

              <button
                type="button"
                style={styles.paginationButton}
                onClick={() =>
                  setCurrentPage((page) => Math.min(totalPages, page + 1))
                }
                disabled={currentPage === totalPages}
              >
                Next
              </button>

              <button
                type="button"
                style={styles.paginationButton}
                onClick={() => setCurrentPage(totalPages)}
                disabled={currentPage === totalPages}
                aria-label="Last page"
              >
                »
              </button>
            </div>
          </div>
        )}

        {lastUpdated && !loading && (
          <p
            style={{
              fontSize: "12px",
              color: "#64748b",
              margin: "16px 0 0",
            }}
          >
            Last updated: {lastUpdated.toLocaleTimeString()}
          </p>
        )}
      </section>
    </div>
  );
}
