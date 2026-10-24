import React, { useState } from "react";
import {
  ActivityIndicator,
  Linking,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

const INITIAL_FORM = {
  age: "",
  sex: "female",
  systolic_bp: "",
  diastolic_bp: "",
  pulse_rate: "",
  height_cm: "",
  weight_kg: "",
  diabetes_history: "no",
  has_existing_hypertension: "no",
};

const MEASUREMENTS = [
  { key: "age", label: "Age (years)", hint: "Research eligibility: 60–74" },
  { key: "systolic_bp", label: "Systolic BP (mmHg)", hint: "Upper BP number" },
  { key: "diastolic_bp", label: "Diastolic BP (mmHg)", hint: "Lower BP number" },
  { key: "pulse_rate", label: "Pulse rate (BPM)", hint: "Beats per minute" },
  { key: "height_cm", label: "Height (cm)", hint: "Centimetres" },
  { key: "weight_kg", label: "Weight (kg)", hint: "Kilograms" },
];

function makeStyles(C) {
  return StyleSheet.create({
    root: { paddingBottom: 20, gap: 16 },
    header: { paddingTop: 8, paddingBottom: 2 },
    kicker: {
      color: C.green,
      fontSize: 11,
      fontWeight: "800",
      letterSpacing: 1.3,
      marginBottom: 8,
    },
    title: {
      color: C.ink,
      fontSize: 27,
      fontWeight: "800",
      lineHeight: 33,
    },
    subtitle: {
      color: C.muted,
      fontSize: 14,
      lineHeight: 20,
      marginTop: 8,
    },
    notice: {
      backgroundColor: C.amberBg,
      borderColor: C.amber,
      borderWidth: 1,
      borderRadius: 12,
      padding: 13,
      gap: 5,
    },
    noticeTitle: { color: C.amber, fontSize: 13, fontWeight: "800" },
    noticeText: { color: C.ink, fontSize: 12, lineHeight: 18 },
    card: {
      backgroundColor: C.white,
      borderColor: C.border,
      borderWidth: 1,
      borderRadius: 16,
      padding: 15,
      gap: 14,
    },
    sectionTitle: { color: C.ink, fontSize: 18, fontWeight: "800" },
    sectionNote: { color: C.muted, fontSize: 12, lineHeight: 18, marginTop: -7 },
    fieldGrid: { flexDirection: "row", flexWrap: "wrap", gap: 12 },
    field: { width: "47%", flexGrow: 1, gap: 6 },
    fieldLabel: { color: C.ink, fontSize: 12, fontWeight: "700" },
    input: {
      backgroundColor: C.bg,
      borderWidth: 1,
      borderColor: C.border,
      borderRadius: 9,
      paddingHorizontal: 11,
      paddingVertical: 10,
      color: C.ink,
      fontSize: 15,
      minHeight: 43,
    },
    hint: { color: C.muted, fontSize: 10, lineHeight: 14 },
    choiceGroup: { gap: 8 },
    choiceLabel: { color: C.ink, fontSize: 12, fontWeight: "700" },
    choices: { flexDirection: "row", gap: 8 },
    choice: {
      flex: 1,
      alignItems: "center",
      justifyContent: "center",
      minHeight: 41,
      paddingVertical: 8,
      paddingHorizontal: 5,
      borderRadius: 9,
      borderWidth: 1,
      borderColor: C.border,
      backgroundColor: C.bg,
    },
    choiceSelected: {
      backgroundColor: C.mint,
      borderColor: C.green,
    },
    choiceText: { color: C.muted, fontSize: 12, fontWeight: "700" },
    choiceTextSelected: { color: C.green },
    button: {
      backgroundColor: C.green,
      borderRadius: 11,
      minHeight: 48,
      alignItems: "center",
      justifyContent: "center",
      paddingHorizontal: 14,
      paddingVertical: 12,
      flexDirection: "row",
      gap: 9,
    },
    buttonDisabled: { opacity: 0.65 },
    buttonText: { color: "#FFFFFF", fontSize: 14, fontWeight: "800" },
    error: {
      backgroundColor: C.redBg,
      borderColor: C.red,
      borderWidth: 1,
      padding: 12,
      borderRadius: 10,
      gap: 4,
    },
    errorText: { color: C.red, fontSize: 12, lineHeight: 18 },
    resultHeader: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
      gap: 8,
    },
    status: {
      color: C.green,
      backgroundColor: C.mint,
      fontSize: 10,
      fontWeight: "800",
      paddingHorizontal: 8,
      paddingVertical: 5,
      borderRadius: 6,
      overflow: "hidden",
    },
    scoreBox: {
      backgroundColor: C.mint,
      borderRadius: 13,
      padding: 15,
      gap: 5,
    },
    scoreLabel: {
      color: C.green,
      fontSize: 11,
      fontWeight: "800",
      letterSpacing: 0.5,
    },
    score: { color: C.forest, fontSize: 37, fontWeight: "800" },
    bodyText: { color: C.ink, fontSize: 12, lineHeight: 18 },
    mutedText: { color: C.muted, fontSize: 11, lineHeight: 17 },
    divider: { height: 1, backgroundColor: C.border },
    feature: { gap: 7, paddingVertical: 8 },
    featureHead: {
      flexDirection: "row",
      alignItems: "flex-start",
      justifyContent: "space-between",
      gap: 8,
    },
    featureName: { flex: 1, color: C.ink, fontSize: 12, fontWeight: "800" },
    featureValue: { color: C.muted, fontSize: 11, marginTop: 3 },
    contribution: { fontSize: 12, fontWeight: "800", textAlign: "right" },
    barTrack: {
      height: 6,
      backgroundColor: C.bg,
      borderRadius: 5,
      overflow: "hidden",
    },
    bar: { height: 6, borderRadius: 5 },
    recommendation: {
      borderWidth: 1,
      borderColor: C.border,
      borderRadius: 11,
      padding: 12,
      gap: 6,
    },
    recommendationTitle: { color: C.ink, fontSize: 13, fontWeight: "800" },
    recommendationText: { color: C.ink, fontSize: 12, lineHeight: 18 },
    source: { color: C.green, fontSize: 11, fontWeight: "700" },
    resetButton: {
      minHeight: 42,
      borderRadius: 9,
      borderWidth: 1,
      borderColor: C.border,
      alignItems: "center",
      justifyContent: "center",
      padding: 10,
    },
    resetText: { color: C.green, fontSize: 12, fontWeight: "800" },
  });
}

function ChoiceGroup({ label, value, choices, onChange, styles }) {
  return (
    <View style={styles.choiceGroup}>
      <Text style={styles.choiceLabel}>{label}</Text>
      <View style={styles.choices}>
        {choices.map((choice) => {
          const selected = value === choice.value;

          return (
            <Pressable
              key={choice.value}
              accessibilityRole="radio"
              accessibilityState={{ selected }}
              onPress={() => onChange(choice.value)}
              style={[
                styles.choice,
                selected && styles.choiceSelected,
              ]}
            >
              <Text
                style={[
                  styles.choiceText,
                  selected && styles.choiceTextSelected,
                ]}
              >
                {choice.label}
              </Text>
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}

function numberLabel(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return String(value ?? "—");
  return Number.isInteger(number) ? String(number) : number.toFixed(2);
}

function signed(value, digits = 2) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "—";
  const prefix = number > 0 ? "+" : "";
  return `${prefix}${number.toFixed(digits)}`;
}

export default function HealthScreen({ apiBase, colors }) {
  const styles = React.useMemo(
    () => makeStyles(colors),
    [colors]
  );

  const [form, setForm] = useState(INITIAL_FORM);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  function update(key, value) {
    setForm((current) => ({ ...current, [key]: value }));
    setError("");
  }

  async function submitAssessment() {
    setError("");
    setResult(null);

    if (!apiBase) {
      setError("The account server address is not available. Check HyperCare connection settings.");
      return;
    }

    for (const field of MEASUREMENTS) {
      if (String(form[field.key]).trim() === "") {
        setError(`Please enter ${field.label.toLowerCase()}.`);
        return;
      }

      if (!Number.isFinite(Number(form[field.key]))) {
        setError(`Please enter a valid number for ${field.label.toLowerCase()}.`);
        return;
      }
    }

    const values = {
      age: Number(form.age),
      systolic_bp: Number(form.systolic_bp),
      diastolic_bp: Number(form.diastolic_bp),
      pulse_rate: Number(form.pulse_rate),
      height_cm: Number(form.height_cm),
      weight_kg: Number(form.weight_kg),
    };

    if (values.age < 60 || values.age > 74) {
      setError("This research model only supports ages 60–74. No score will be requested for an age outside that range.");
      return;
    }

    if (values.systolic_bp < 70 || values.systolic_bp > 300) {
      setError("Enter systolic blood pressure between 70 and 300 mmHg.");
      return;
    }

    if (values.diastolic_bp < 30 || values.diastolic_bp > 180) {
      setError("Enter diastolic blood pressure between 30 and 180 mmHg.");
      return;
    }

    if (values.pulse_rate < 30 || values.pulse_rate > 200) {
      setError("Enter a pulse rate between 30 and 200 BPM.");
      return;
    }

    if (values.height_cm < 100 || values.height_cm > 220) {
      setError("Enter height between 100 and 220 cm.");
      return;
    }

    if (values.weight_kg < 25 || values.weight_kg > 300) {
      setError("Enter weight between 25 and 300 kg.");
      return;
    }

    const payload = {
      ...values,
      sex: form.sex,
      diabetes_history: form.diabetes_history === "yes",
      has_existing_hypertension:
        form.has_existing_hypertension === "yes",
    };

    const base = apiBase.replace(/\/+$/, "");
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 25000);

    setLoading(true);

    try {
      const response = await fetch(
        `${base}/api/component1/predict`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Accept: "application/json",
          },
          body: JSON.stringify(payload),
          signal: controller.signal,
        }
      );

      const raw = await response.text();
      let data;

      try {
        data = JSON.parse(raw);
      } catch {
        throw new Error("The AI service returned an unexpected response.");
      }

      if (!response.ok) {
        const detail = Array.isArray(data.detail)
          ? data.detail.map((item) => item.msg || "Invalid input").join("; ")
          : data.detail;

        throw new Error(
          data.error ||
          detail ||
          data.message ||
          `Assessment failed (HTTP ${response.status}).`
        );
      }

      setResult(data);
    } catch (err) {
      if (err.name === "AbortError") {
        setError("The assessment timed out. Check that Express and the Component 1 Python service are running.");
      } else {
        setError(
          err.message ||
          "The assessment could not be completed. Check the backend connection and try again."
        );
      }
    } finally {
      clearTimeout(timer);
      setLoading(false);
    }
  }

  function resetAssessment() {
    setResult(null);
    setError("");
  }

  const shap = result?.shap_explanation;
  const features = Array.isArray(shap?.features) ? shap.features : [];
  const recommendations = Array.isArray(result?.recommendations)
    ? result.recommendations
    : [];
  const warnings = Array.isArray(result?.domain_warnings)
    ? result.domain_warnings
    : [];
  const hasScore = typeof result?.model_score_percent === "number";
  const maxContribution = Math.max(
    0,
    ...features.map((item) => Math.abs(Number(item.contribution) || 0))
  );

  return (
    <View style={styles.root}>
      <View style={styles.header}>
        <Text style={styles.kicker}>COMPONENT 1 · PHYSIOLOGICAL WELLNESS</Text>
        <Text style={styles.title}>Health & blood pressure</Text>
        <Text style={styles.subtitle}>
          Review a resident’s measurements, the research-model output,
          its SHAP explanation, and general wellness guidance.
        </Text>
      </View>

      <View style={styles.notice}>
        <Text style={styles.noticeTitle}>Research prototype — not a diagnosis</Text>
        <Text style={styles.noticeText}>
          The model was developed using historical data from participants
          aged 60–74 who met specific study criteria. Its output is
          uncalibrated and is not a validated absolute risk for a fixed
          time period. Follow the care home’s clinical assessment process.
        </Text>
      </View>

      <View style={styles.card}>
        <Text style={styles.sectionTitle}>Resident measurements</Text>
        <Text style={styles.sectionNote}>
          Enter verified measurements. Height and weight are used to
          calculate BMI by the existing Python service.
        </Text>

        <View style={styles.fieldGrid}>
          {MEASUREMENTS.map((field) => (
            <View key={field.key} style={styles.field}>
              <Text style={styles.fieldLabel}>{field.label}</Text>
              <TextInput
                accessibilityLabel={field.label}
                value={form[field.key]}
                onChangeText={(value) => update(field.key, value)}
                keyboardType="numeric"
                style={styles.input}
                placeholder="Enter value"
                placeholderTextColor={colors.muted}
                editable={!loading}
              />
              <Text style={styles.hint}>{field.hint}</Text>
            </View>
          ))}
        </View>

        <ChoiceGroup
          label="Sex"
          value={form.sex}
          choices={[
            { label: "Female", value: "female" },
            { label: "Male", value: "male" },
          ]}
          onChange={(value) => update("sex", value)}
          styles={styles}
        />

        <ChoiceGroup
          label="Reported diabetes history"
          value={form.diabetes_history}
          choices={[
            { label: "No", value: "no" },
            { label: "Yes", value: "yes" },
          ]}
          onChange={(value) => update("diabetes_history", value)}
          styles={styles}
        />

        <ChoiceGroup
          label="Already diagnosed with hypertension?"
          value={form.has_existing_hypertension}
          choices={[
            { label: "No known diagnosis", value: "no" },
            { label: "Already diagnosed", value: "yes" },
          ]}
          onChange={(value) =>
            update("has_existing_hypertension", value)
          }
          styles={styles}
        />

        <Text style={styles.hint}>
          Residents with an existing diagnosis follow a separate response
          pathway. The first-onset model does not generate a score for them.
        </Text>

        <Pressable
          accessibilityRole="button"
          disabled={loading}
          onPress={submitAssessment}
          style={[styles.button, loading && styles.buttonDisabled]}
        >
          {loading && <ActivityIndicator color="#FFFFFF" />}
          <Text style={styles.buttonText}>
            {loading ? "Assessing measurements…" : "Generate AI assessment"}
          </Text>
        </Pressable>

        {!!error && (
          <View accessibilityLiveRegion="polite" style={styles.error}>
            <Text style={styles.errorText}>{error}</Text>
          </View>
        )}
      </View>

      {result && (
        <View style={styles.card} accessibilityLiveRegion="polite">
          <View style={styles.resultHeader}>
            <Text style={styles.sectionTitle}>Assessment result</Text>
            <Text style={styles.status}>
              {String(result.status || "Response received").replace(/_/g, " ")}
            </Text>
          </View>

          {hasScore ? (
            <View style={styles.scoreBox}>
              <Text style={styles.scoreLabel}>
                {result.model_name || "Research model"} · model output
              </Text>
              <Text style={styles.score}>
                {result.model_score_percent.toFixed(2)}%
              </Text>
              <Text style={styles.bodyText}>
                {result.score_interpretation ||
                  "This is a research-model output, not a diagnosis."}
              </Text>
            </View>
          ) : (
            <View style={styles.notice}>
              <Text style={styles.noticeTitle}>No model score generated</Text>
              <Text style={styles.noticeText}>
                {result.message ||
                  "The current model could not generate an eligible score for these inputs."}
              </Text>
            </View>
          )}

          {warnings.length > 0 && (
            <View style={styles.notice}>
              <Text style={styles.noticeTitle}>Research-data warnings</Text>
              {warnings.map((warning, index) => (
                <Text key={`${index}-${warning}`} style={styles.noticeText}>
                  • {warning}
                </Text>
              ))}
            </View>
          )}

          {hasScore && features.length > 0 && (
            <>
              <View style={styles.divider} />
              <Text style={styles.sectionTitle}>SHAP explanation</Text>
              <Text style={styles.mutedText}>
                Contributions describe how each input moves this model’s
                output. They are explanatory associations, not causes.
                Positive values increase model output; negative values
                decrease it.
              </Text>

              {features.map((item, index) => {
                const contribution = Number(item.contribution) || 0;
                const pp = item.contribution_percentage_points;
                const isPoints = typeof pp === "number";
                const width =
                  maxContribution > 0
                    ? Math.abs(contribution) / maxContribution * 100
                    : 0;
                const increases = contribution > 0;

                return (
                  <View
                    key={`${item.feature || item.label || "feature"}-${index}`}
                    style={styles.feature}
                  >
                    <View style={styles.featureHead}>
                      <View style={{ flex: 1 }}>
                        <Text style={styles.featureName}>
                          {item.label || item.feature || "Feature"}
                        </Text>
                        <Text style={styles.featureValue}>
                          Input value: {numberLabel(item.value)}
                        </Text>
                      </View>
                      <Text
                        style={[
                          styles.contribution,
                          { color: increases ? colors.red : colors.green },
                        ]}
                      >
                        {isPoints
                          ? `${signed(pp)} pp`
                          : signed(contribution, 4)}
                      </Text>
                    </View>
                    <View style={styles.barTrack}>
                      <View
                        style={[
                          styles.bar,
                          {
                            width: `${width}%`,
                            backgroundColor: increases
                              ? colors.red
                              : colors.green,
                          },
                        ]}
                      />
                    </View>
                    <Text style={styles.hint}>
                      {item.direction === "increases_model_output"
                        ? "Increases model output"
                        : item.direction === "decreases_model_output"
                          ? "Decreases model output"
                          : "No material directional contribution"}
                    </Text>
                  </View>
                );
              })}

              {shap?.reconstruction_verified && (
                <Text style={styles.hint}>
                  The SHAP contributions reconstruct the model probability
                  within the service’s configured tolerance. The displayed
                  percentage-point contributions are on the model output
                  scale, not a validated clinical-risk scale.
                </Text>
              )}
            </>
          )}

          {recommendations.length > 0 && (
            <>
              <View style={styles.divider} />
              <Text style={styles.sectionTitle}>Wellness recommendations</Text>
              <Text style={styles.mutedText}>
                General precautionary guidance returned by the service.
                These recommendations are not treatment instructions and
                are not causal conclusions from SHAP.
              </Text>

              {recommendations.map((item, index) => {
                const match = String(item.source || "").match(
                  /https?:\/\/\S+/
                );

                return (
                  <View
                    key={`${item.title || "recommendation"}-${index}`}
                    style={styles.recommendation}
                  >
                    <Text style={styles.recommendationTitle}>
                      {item.title || "Recommendation"}
                    </Text>
                    {!!item.reason && (
                      <Text style={styles.mutedText}>{item.reason}</Text>
                    )}
                    {!!item.action && (
                      <Text style={styles.recommendationText}>
                        {item.action}
                      </Text>
                    )}
                    {!!match && (
                      <Pressable
                        accessibilityRole="link"
                        onPress={() => Linking.openURL(match[0])}
                      >
                        <Text style={styles.source}>View source ↗</Text>
                      </Pressable>
                    )}
                  </View>
                );
              })}
            </>
          )}

          <Pressable
            accessibilityRole="button"
            onPress={resetAssessment}
            style={styles.resetButton}
          >
            <Text style={styles.resetText}>Start a new assessment</Text>
          </Pressable>
        </View>
      )}
    </View>
  );
}