
import React, { useState } from "react";
import "./Register.css";

const API_URL = "http://localhost:5000/api/auth";

export default function Register({ onRegisterSuccess, onLogin }) {
  const [form, setForm] = useState({
    name: "",
    email: "",
    password: "",
    confirmPassword: "",
    phone: "",
    careHome: "",
    role: "caregiver",
  });

  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  function updateField(event) {
    const { name, value } = event.target;
    setForm((current) => ({ ...current, [name]: value }));
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");

    if (form.password !== form.confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    if (
      form.password.length < 10 ||
      form.password.length > 128
    ) {
      setError("Password must be between 10 and 128 characters.");
      return;
    }

    setLoading(true);

    try {
      const response = await fetch(`${API_URL}/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: form.name.trim(),
          email: form.email.trim(),
          password: form.password,
          phone: form.phone.trim(),
          careHome: form.careHome.trim(),
          role: form.role,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || "Registration failed.");
      }

      if (!data.token || !data.user) {
        throw new Error(
          "The server returned an invalid registration response."
        );
      }

      onRegisterSuccess(data);
    } catch (err) {
      setError(
        err.message === "Failed to fetch"
          ? "Cannot connect to the server. Check that the backend is running."
          : err.message
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="auth-page">
      <section className="auth-card auth-card-register">
        <div className="auth-brand-mark">H</div>

        <p className="auth-eyebrow">HYPERCARE PORTAL</p>

        <h1>Create your account</h1>

        <p className="auth-subtitle">
          Register to access the elderly-care management workspace.
        </p>

        <form onSubmit={handleSubmit} className="auth-form">
          <label htmlFor="register-name">Full name</label>
          <input
            id="register-name"
            name="name"
            value={form.name}
            onChange={updateField}
            autoComplete="name"
            placeholder="Your full name"
            maxLength={100}
            required
          />

          <label htmlFor="register-email">Email address</label>
          <input
            id="register-email"
            name="email"
            type="email"
            value={form.email}
            onChange={updateField}
            autoComplete="email"
            placeholder="you@example.com"
            maxLength={254}
            required
          />

          <label htmlFor="register-role">Account type</label>
          <select
            id="register-role"
            name="role"
            value={form.role}
            onChange={updateField}
            required
          >
            <option value="caregiver">Caregiver</option>
            <option value="patient">Patient</option>
          </select>

          <label htmlFor="register-phone">Phone number</label>
          <input
            id="register-phone"
            name="phone"
            type="tel"
            value={form.phone}
            onChange={updateField}
            autoComplete="tel"
            placeholder="Phone number (optional)"
            maxLength={30}
          />

          <label htmlFor="register-care-home">Care home</label>
          <input
            id="register-care-home"
            name="careHome"
            value={form.careHome}
            onChange={updateField}
            placeholder="Care home name (optional)"
            maxLength={200}
          />

          <label htmlFor="register-password">Password</label>
          <input
            id="register-password"
            name="password"
            type="password"
            value={form.password}
            onChange={updateField}
            autoComplete="new-password"
            placeholder="At least 10 characters"
            minLength={10}
            maxLength={128}
            required
          />

          <label htmlFor="register-confirm-password">
            Confirm password
          </label>
          <input
            id="register-confirm-password"
            name="confirmPassword"
            type="password"
            value={form.confirmPassword}
            onChange={updateField}
            autoComplete="new-password"
            placeholder="Enter your password again"
            minLength={10}
            maxLength={128}
            required
          />

          {error && (
            <p className="auth-error" role="alert">
              {error}
            </p>
          )}

          <button
            className="auth-submit"
            type="submit"
            disabled={loading}
          >
            {loading ? "Creating account..." : "Create account"}
          </button>
        </form>

        <p className="auth-switch">
          Already have an account?{" "}
          <button type="button" onClick={onLogin}>
            Sign in
          </button>
        </p>

        <p className="auth-footer">
          HyperCare · Elderly-care management
        </p>
      </section>
    </main>
  );
}
