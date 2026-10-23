import React from "react";
import "./HomePage.css";

export const CARE_MODULES = [
  {
    id: "mental",
    number: "01",
    navLabel: "Wellness",
    icon: "wellness",
    category: "WELLBEING & PHYSIOLOGY",
    title: "Mental & Physiological Wellness",
    description:
      "Explore physiological measurements and wellbeing information within the resident-care workflow.",
    features: [
      "Physiological information",
      "Wellbeing assessment",
    ],
    action: "Open wellness workspace",
  },
  {
    id: "nutrition",
    number: "02",
    navLabel: "Nutrition",
    icon: "nutrition",
    category: "MEALS & NUTRITION",
    title: "Personalized Nutritional Intelligence",
    description:
      "Review meal information, nutrient analysis and nutrition assessment in one dedicated workspace.",
    features: [
      "Meal information",
      "Nutritional assessment",
    ],
    action: "Open nutrition workspace",
  },
  {
    id: "medicine",
    number: "03",
    navLabel: "Medicines",
    icon: "medicine",
    category: "PRESCRIPTIONS & MEDICINES",
    title: "Medicine Intelligence & Verification",
    description:
      "Extract prescription instructions, review medicine details and compare a photographed medicine tray.",
    features: [
      "Prescription review",
      "Tray comparison",
    ],
    action: "Open medicine workspace",
  },
  {
    id: "monitoring",
    number: "04",
    navLabel: "Monitoring",
    icon: "monitoring",
    category: "ACTIVITY & RESIDENT SAFETY",
    title: "Smart Patient Monitoring",
    description:
      "Access the patient-monitoring workspace for movement observations and resident-safety information.",
    features: [
      "Activity observations",
      "Safety monitoring",
    ],
    action: "Open monitoring workspace",
  },
];

export function CareIcon({ name, className = "" }) {
  const shapes = {
    home: (
      <>
        <path d="m3 10 9-7 9 7" />
        <path d="M5 9v12h14V9M9 21v-7h6v7" />
      </>
    ),

    wellness: (
      <>
        <path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1.1-1.1a5.5 5.5 0 0 0-7.8 7.8L12 21l8.8-8.6a5.5 5.5 0 0 0 0-7.8Z" />
        <path d="M4 12h4l2-4 3 8 2-4h5" />
      </>
    ),

    nutrition: (
      <>
        <path d="M5 3v6a2 2 0 0 0 4 0V3M7 3v18M18 3c-3 3-4 6-3 9h4M19 3v18" />
      </>
    ),

    medicine: (
      <>
        <path d="m9 4-5 5a6.4 6.4 0 0 0 9 9l5-5a6.4 6.4 0 0 0-9-9Z" />
        <path d="m7 7 9 9" />
      </>
    ),

    monitoring: (
      <>
        <circle cx="12" cy="5" r="2" />
        <path d="m8 22 2-7-3-3 3-4h4l3 4h4M10 8l-1 6 5 2 2 6M3 12h3" />
      </>
    ),

    arrow: (
      <path d="M4 12h16m-6-6 6 6-6 6" />
    ),

    check: (
      <path d="m5 12 4 4L19 6" />
    ),

    shield: (
      <>
        <path d="m12 3 8 3v6c0 5-8 9-8 9S4 17 4 12V6l8-3Z" />
        <path d="m8 12 3 3 5-6" />
      </>
    ),
  };

  return (
    <svg
      className={`hc-icon ${className}`}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {shapes[name] || shapes.home}
    </svg>
  );
}

export default function HomePage({ onNavigate }) {
  return (
    <main className="hc-home">
      <section
        className="hc-hero"
        aria-labelledby="hc-home-title"
      >
        <div className="hc-hero-copy">
          <p className="hc-eyebrow">
            <span />
            HYPERTENSION MANAGEMENT FOR ELDERLY CARE
          </p>

          <h1 id="hc-home-title">
            Four care areas.
            <br />
            <em>One shared purpose.</em>
          </h1>

          <p className="hc-hero-description">
            A connected workspace for caregivers to review wellbeing,
            nutrition, medicines and resident monitoring throughout
            everyday care.
          </p>

          <div className="hc-hero-actions">
            <a
              className="hc-primary-link"
              href="#hc-workspaces"
            >
              Explore care workspaces
              <CareIcon name="arrow" />
            </a>

            <a
              className="hc-text-link"
              href="#hc-how-it-works"
            >
              How it works
              <span aria-hidden="true">↗</span>
            </a>
          </div>

          <div className="hc-hero-note">
            <CareIcon name="shield" />
            <span>
              Designed to support caregiver review and informed
              follow-up.
            </span>
          </div>
        </div>

        <aside
          className="hc-care-map"
          aria-label="Four care workspaces"
        >
          <div className="hc-map-heading">
            <span className="hc-map-label">
              THE CONNECTED CARE WORKSPACE
            </span>
            <span className="hc-map-count">04</span>
          </div>

          <h2>
            Care, considered
            <br />
            from every angle.
          </h2>

          <p>
            Choose the area you need. Keep the resident at the centre.
          </p>

          <div className="hc-map-list">
            {CARE_MODULES.map((module) => (
              <button
                type="button"
                key={module.id}
                onClick={() => onNavigate(module.id)}
                className="hc-map-item"
                aria-label={module.action}
              >
                <span className="hc-map-icon">
                  <CareIcon name={module.icon} />
                </span>

                <span className="hc-map-item-name">
                  {module.navLabel === "Wellness"
                    ? "Wellbeing & physiology"
                    : module.navLabel === "Monitoring"
                      ? "Activity & resident safety"
                      : module.title.split(" ")[0] === "Personalized"
                        ? "Meals & nutritional care"
                        : "Medicines & prescriptions"}
                </span>

                <CareIcon name="arrow" />
              </button>
            ))}
          </div>

          <div className="hc-map-footer">
            <span className="hc-map-dot" />
            A research platform for elderly-care homes
          </div>
        </aside>
      </section>

      <section
        className="hc-workspaces"
        id="hc-workspaces"
        aria-labelledby="hc-workspaces-title"
      >
        <div className="hc-section-heading">
          <div>
            <p className="hc-eyebrow">YOUR CARE WORKSPACES</p>
            <h2 id="hc-workspaces-title">
              The right tools for each part of care.
            </h2>
          </div>

          <p>
            Four dedicated areas.
            <br />
            A clear starting point for your work.
          </p>
        </div>

        <div className="hc-module-grid">
          {CARE_MODULES.map((module) => (
            <article
              className={`hc-module-card hc-module-${module.id}`}
              key={module.id}
            >
              <div className="hc-card-top">
                <span className="hc-card-icon">
                  <CareIcon name={module.icon} />
                </span>

                <span className="hc-card-number">
                  WORKSPACE {module.number}
                </span>
              </div>

              <p className="hc-card-category">
                {module.category}
              </p>

              <h3>{module.title}</h3>

              <p className="hc-card-description">
                {module.description}
              </p>

              <ul className="hc-feature-list">
                {module.features.map((feature) => (
                  <li key={feature}>
                    <CareIcon name="check" />
                    {feature}
                  </li>
                ))}
              </ul>

              <button
                type="button"
                className="hc-card-action"
                onClick={() => onNavigate(module.id)}
              >
                <span>{module.action}</span>
                <CareIcon name="arrow" />
              </button>
            </article>
          ))}
        </div>
      </section>

      <section
        className="hc-process"
        id="hc-how-it-works"
        aria-labelledby="hc-process-title"
      >
        <div className="hc-process-intro">
          <p className="hc-eyebrow">A SIMPLE WAY TO BEGIN</p>

          <h2 id="hc-process-title">
            Built around the caregiver.
          </h2>

          <p>
            Start with the relevant care area and review its
            information in context.
          </p>
        </div>

        <ol className="hc-process-list">
          <li>
            <span>01</span>
            <div>
              <h3>Choose a workspace</h3>
              <p>
                Open the care component relevant to the task at hand.
              </p>
            </div>
          </li>

          <li>
            <span>02</span>
            <div>
              <h3>Review the information</h3>
              <p>
                Use the records and assessment tools provided within
                that component.
              </p>
            </div>
          </li>

          <li>
            <span>03</span>
            <div>
              <h3>Check before acting</h3>
              <p>
                Review model outputs alongside the original information
                and appropriate professional judgement.
              </p>
            </div>
          </li>
        </ol>
      </section>

      <footer className="hc-home-footer">
        <div>
          <strong>HyperCare</strong>
          <span>Elderly-care hypertension management</span>
        </div>

        <p>
          Research prototype · AI outputs require human review.
          <br />
          This platform does not independently confirm treatment safety.
        </p>
      </footer>
    </main>
  );
}