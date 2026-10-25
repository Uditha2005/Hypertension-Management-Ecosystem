import { useAppTheme } from "./CareAccount";
import React, { useState } from "react";
import {
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

const C = {
  background: "#F2F5F2",
  white: "#FFFFFF",
  forest: "#123F35",
  green: "#187E63",
  mint: "#E5F2E9",
  ink: "#20372D",
  muted: "#728078",
  border: "#DDE6DE",
};

const MODULES = [
  {
    id: "health",
    number: "01",
    symbol: "BP",
    title: "Health & BP\nMonitoring",
    description: "Blood pressure and physiological health insights.",
    color: "#246F59",
    background: "#E5F2E9",
    heading: "A clearer view of resident health.",
    overview:
      "This workspace is reserved for your team’s physiological hypertension monitoring component.",
    sections: [
      {
        title: "Blood pressure records",
        text: "A place for resident blood pressure measurements and trends.",
      },
      {
        title: "Physiological assessment",
        text: "A place for the component’s trained-model assessment and supporting information.",
      },
      {
        title: "Caregiver review",
        text: "A place to review assessment results alongside the resident’s records.",
      },
    ],
  },
  {
    id: "activity",
    number: "02",
    symbol: "↗",
    title: "Activity &\nSafety",
    description: "Movement monitoring and resident safety support.",
    color: "#54704A",
    background: "#ECF1E5",
    heading: "Support safer everyday movement.",
    overview:
      "This workspace is reserved for your team’s activity and resident-safety component.",
    sections: [
      {
        title: "Activity monitoring",
        text: "A place for the component’s movement and activity observations.",
      },
      {
        title: "Safety assessment",
        text: "A place for model outputs relevant to resident safety.",
      },
      {
        title: "Observation history",
        text: "A place to revisit recorded observations and caregiver reviews.",
      },
    ],
  },
  {
    id: "nutrition",
    number: "03",
    symbol: "N",
    title: "Nutrition\nCare",
    description: "Meal information and nutrition assessment.",
    color: "#6D7045",
    background: "#F1F1E4",
    heading: "Bring nutrition into daily care.",
    overview:
      "This workspace is reserved for your team’s nutritional-intelligence component.",
    sections: [
      {
        title: "Meal records",
        text: "A place to enter and review resident meal information.",
      },
      {
        title: "Nutrient analysis",
        text: "A place for the component’s nutrient processing and assessment.",
      },
      {
        title: "Nutrition insights",
        text: "A place to view the trained model’s results and supporting details.",
      },
    ],
  },
  {
    id: "medicine",
    number: "04",
    symbol: "Rx",
    title: "Medicine\nVerification",
    description: "Prescription review and medicine tray comparison.",
    color: "#28756C",
    background: "#E4F1ED",
  },
];

function HomeButton({ title, onPress, secondary = false, disabled = false }) {
  const { colors: C, isDark } = useAppTheme();
  const styles = React.useMemo(() => makeHomeStyles(C), [C]);

  return (
    <Pressable
      accessibilityRole="button"
      disabled={disabled}
      onPress={onPress}
      style={({ pressed }) => [
        styles.button,
        secondary && styles.secondaryButton,
        (pressed || disabled) && {
          opacity: disabled ? 0.45 : 0.75,
        },
      ]}
    >
      <Text
        style={[
          styles.buttonText,
          secondary && { color: C.green },
        ]}
      >
        {title}
      </Text>
    </Pressable>
  );
}

export default function HomeScreen({
  onOpenMedicine,
  onOpenNutrition,
  onOpenHistory,
  onConnect,
  connection = "Not connected",
  modelReady = false,
  hasReview = false,
  busy = false,
}) {
  const { colors: C, isDark } = useAppTheme();
  const styles = React.useMemo(() => makeHomeStyles(C), [C]);

  const [selectedModule, setSelectedModule] = useState(null);

  function openModule(module) {
    if (busy) return;

    if (module.id === "medicine") {
      onOpenMedicine();
      return;
    }

    if (module.id === "nutrition") {
      onOpenNutrition();
      return;
    }

    setSelectedModule(module);
  }

  return (
    <>
      <View style={styles.intro}>
        <View style={styles.facilityLabel}>
          <View style={styles.labelDot} />
          <Text style={styles.facilityLabelText}>
            ELDERLY-CARE WORKSPACE
          </Text>
        </View>

        <Text style={styles.title}>
          Connected care.{"\n"}
          Every day.
        </Text>

        <Text style={styles.subtitle}>
          Hypertension management for elderly-care homes, bringing health,
          activity, nutrition and medicines together.
        </Text>
      </View>

      <View style={styles.hero}>
        <View style={styles.heroTop}>
          <Text style={styles.heroEyebrow}>ONE CONNECTED SYSTEM</Text>
          <View style={styles.heroBadge}>
            <Text style={styles.heroBadgeText}>4 care areas</Text>
          </View>
        </View>

        <Text style={styles.heroTitle}>
          A fuller picture{"\n"}of everyday care.
        </Text>

        <Text style={styles.heroDescription}>
          Help caregivers review the information that matters across each
          part of a resident’s care.
        </Text>

        <View style={styles.carePath}>
          {[
            ["01", "Health"],
            ["02", "Activity"],
            ["03", "Nutrition"],
            ["04", "Medicines"],
          ].map(([number, title]) => (
            <View key={number} style={styles.carePathItem}>
              <View style={styles.carePathNumber}>
                <Text style={styles.carePathNumberText}>{number}</Text>
              </View>
              <Text style={styles.carePathLabel}>{title}</Text>
            </View>
          ))}
        </View>
      </View>

      <View style={styles.sectionHeader}>
        <View>
          <Text style={styles.sectionEyebrow}>CARE COMPONENTS</Text>
          <Text style={styles.sectionTitle}>Choose a workspace</Text>
        </View>
        <Text style={styles.sectionCaption}>Explore all four</Text>
      </View>

      <View style={styles.moduleGrid}>
        {MODULES.map((module) => {
          const medicine = module.id === "medicine";

          return (
            <View key={module.id} style={styles.moduleSlot}>
              <Pressable
                accessibilityRole="button"
                accessibilityLabel={`Open ${module.title.replace("\n", " ")}`}
                disabled={busy}
                onPress={() => openModule(module)}
                style={({ pressed }) => [
                  styles.moduleCard,
                  pressed && { opacity: 0.78 },
                  busy && { opacity: 0.6 },
                ]}
              >
                <View style={styles.moduleTop}>
                  <View
                    style={[
                      styles.moduleIcon,
                      { backgroundColor: (isDark ? C.mint : module.background) },
                    ]}
                  >
                    <Text
                      style={[
                        styles.moduleSymbol,
                        { color: (isDark ? C.green : module.color) },
                      ]}
                    >
                      {module.symbol}
                    </Text>
                  </View>
                  <Text style={styles.moduleNumber}>{module.number}</Text>
                </View>

                <Text style={styles.moduleTitle}>{module.title}</Text>

                <Text style={styles.moduleDescription}>
                  {module.description}
                </Text>

                <View style={styles.moduleBottom}>
                  <Text
                    style={[
                      styles.moduleAction,
                      { color: (isDark ? C.green : module.color) },
                    ]}
                  >
                    {medicine ? "Open workspace" : "View module"}
                  </Text>
                  <Text
                    style={[
                      styles.moduleArrow,
                      { color: (isDark ? C.green : module.color) },
                    ]}
                  >
                    →
                  </Text>
                </View>

                {medicine && hasReview && (
                  <View style={styles.resumeTag}>
                    <Text style={styles.resumeTagText}>
                      Review in progress
                    </Text>
                  </View>
                )}
              </Pressable>
            </View>
          );
        })}
      </View>

      <View style={styles.noteCard}>
        <View style={styles.noteIcon}>
          <Text style={styles.noteIconText}>i</Text>
        </View>
        <View style={styles.flex}>
          <Text style={styles.noteTitle}>Built around caregiver review</Text>
          <Text style={styles.noteDescription}>
            AI outputs support the review process. Resident care decisions
            require the appropriate professional assessment.
          </Text>
        </View>
      </View>

      <View style={styles.sectionHeader}>
        <View>
          <Text style={styles.sectionEyebrow}>WORKSPACE TOOLS</Text>
          <Text style={styles.sectionTitle}>Continue your work</Text>
        </View>
      </View>

      <Pressable
        accessibilityRole="button"
        disabled={busy}
        onPress={onOpenHistory}
        style={styles.historyCard}
      >
        <View style={styles.historyIcon}>
          <Text style={styles.historyIconText}>≡</Text>
        </View>
        <View style={styles.flex}>
          <Text style={styles.historyTitle}>Medicine review history</Text>
          <Text style={styles.historyDescription}>
            Revisit saved tray comparisons.
          </Text>
        </View>
        <Text style={styles.historyArrow}>→</Text>
      </Pressable>

      <View style={styles.connectionCard}>
        <View style={styles.connectionHeader}>
          <Text style={styles.connectionTitle}>Medicine API connection</Text>
          <View
            style={[
              styles.statusPill,
              {
                backgroundColor: modelReady ? C.mint : "#F0F1ED",
              },
            ]}
          >
            <View
              style={[
                styles.statusDot,
                { backgroundColor: modelReady ? C.green : C.muted },
              ]}
            />
            <Text
              style={[
                styles.statusText,
                { color: modelReady ? C.green : C.muted },
              ]}
            >
              {connection}
            </Text>
          </View>
        </View>

        <Text style={styles.connectionDescription}>
          {modelReady
            ? "The medicine service is available. Other care services can be connected independently."
            : "Connect the laptop medicine service to use prescription extraction and tray comparison."}
        </Text>

        <HomeButton
          title={modelReady ? "Refresh connection" : "Retry connection"}
          secondary
          disabled={busy}
          onPress={onConnect}
        />
      </View>

      <Modal
        visible={selectedModule !== null}
        animationType="slide"
        onRequestClose={() => setSelectedModule(null)}
      >
        <SafeAreaView style={styles.modal}>
          <ScrollView contentContainerStyle={styles.modalContent}>
            <Pressable
              accessibilityRole="button"
              onPress={() => setSelectedModule(null)}
              style={styles.backButton}
            >
              <Text style={styles.backButtonText}>← Back to Home</Text>
            </Pressable>

            {selectedModule && (
              <>
                <View
                  style={[
                    styles.largeModuleIcon,
                    { backgroundColor: (isDark ? C.mint : selectedModule.background) },
                  ]}
                >
                  <Text
                    style={[
                      styles.largeModuleSymbol,
                      { color: (isDark ? C.green : selectedModule.color) },
                    ]}
                  >
                    {selectedModule.symbol}
                  </Text>
                </View>

                <Text style={styles.sectionEyebrow}>
                  CARE COMPONENT {selectedModule.number}
                </Text>

                <Text style={styles.modalTitle}>
                  {selectedModule.title.replace("\n", " ")}
                </Text>

                <Text style={styles.modalHeading}>
                  {selectedModule.heading}
                </Text>

                <View style={styles.integrationNotice}>
                  <Text style={styles.integrationTitle}>
                    Module integration pending
                  </Text>
                  <Text style={styles.integrationDescription}>
                    {selectedModule.overview} No resident measurements,
                    predictions or alerts are connected on this screen yet.
                  </Text>
                </View>

                <Text style={styles.sectionTitle}>Workspace overview</Text>

                {selectedModule.sections.map((section, index) => (
                  <View key={section.title} style={styles.overviewCard}>
                    <View style={styles.overviewNumber}>
                      <Text style={styles.overviewNumberText}>
                        {index + 1}
                      </Text>
                    </View>

                    <View style={styles.flex}>
                      <Text style={styles.overviewTitle}>
                        {section.title}
                      </Text>
                      <Text style={styles.overviewText}>{section.text}</Text>
                    </View>
                  </View>
                ))}

                <HomeButton
                  title="Return to Home"
                  onPress={() => setSelectedModule(null)}
                />
              </>
            )}
          </ScrollView>
        </SafeAreaView>
      </Modal>
    </>
  );
}

function makeHomeStyles(C) {
  return StyleSheet.create({
  flex: {
    flex: 1,
  },
  intro: {
    paddingTop: 2,
    paddingBottom: 24,
  },
  facilityLabel: {
    flexDirection: "row",
    alignItems: "center",
    gap: 7,
    marginBottom: 16,
  },
  labelDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: C.green,
  },
  facilityLabelText: {
    color: C.green,
    fontSize: 9,
    fontWeight: "800",
    letterSpacing: 1.5,
  },
  title: {
    color: C.ink,
    fontSize: 36,
    lineHeight: 43,
    fontWeight: "800",
    letterSpacing: -1.4,
    marginBottom: 12,
  },
  subtitle: {
    color: C.muted,
    fontSize: 13,
    lineHeight: 22,
    maxWidth: 420,
  },
  hero: {
    backgroundColor: "#123F35",
    borderRadius: 25,
    padding: 23,
    marginBottom: 29,
  },
  heroTop: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    gap: 10,
    flexWrap: "wrap",
  },
  heroEyebrow: {
    color: "#A5CDB4",
    fontSize: 9,
    fontWeight: "800",
    letterSpacing: 1.3,
  },
  heroBadge: {
    backgroundColor: "#285347",
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 8,
  },
  heroBadgeText: {
    color: "#D7EADB",
    fontSize: 9,
    fontWeight: "700",
  },
  heroTitle: {
    color: C.white,
    fontSize: 28,
    lineHeight: 35,
    fontWeight: "800",
    letterSpacing: -0.7,
    marginTop: 21,
    marginBottom: 12,
  },
  heroDescription: {
    color: "#C2D8C9",
    fontSize: 12,
    lineHeight: 21,
  },
  carePath: {
    flexDirection: "row",
    marginTop: 26,
    paddingTop: 20,
    borderTopWidth: 1,
    borderTopColor: "#356052",
  },
  carePathItem: {
    flex: 1,
    alignItems: "center",
    gap: 8,
  },
  carePathNumber: {
    width: 31,
    height: 31,
    borderRadius: 11,
    backgroundColor: "#2A5547",
    alignItems: "center",
    justifyContent: "center",
  },
  carePathNumberText: {
    color: "#D3E9DA",
    fontSize: 10,
    fontWeight: "800",
  },
  carePathLabel: {
    color: "#D3E3D7",
    fontSize: 9,
    fontWeight: "600",
  },
  sectionHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-end",
    gap: 10,
    marginBottom: 16,
    flexWrap: "wrap",
  },
  sectionEyebrow: {
    color: C.green,
    fontSize: 9,
    fontWeight: "800",
    letterSpacing: 1.3,
    marginBottom: 7,
  },
  sectionTitle: {
    color: C.ink,
    fontSize: 19,
    fontWeight: "800",
    letterSpacing: -0.4,
  },
  sectionCaption: {
    color: C.muted,
    fontSize: 10,
    paddingBottom: 2,
  },
  moduleGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    marginHorizontal: -6,
    marginBottom: 14,
  },
  moduleSlot: {
    width: "50%",
    paddingHorizontal: 6,
    paddingBottom: 12,
  },
  moduleCard: {
    flex: 1,
    backgroundColor: C.white,
    borderWidth: 1,
    borderColor: C.border,
    borderRadius: 20,
    padding: 16,
    minHeight: 245,
  },
  moduleTop: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    gap: 8,
    marginBottom: 16,
  },
  moduleIcon: {
    width: 44,
    height: 44,
    borderRadius: 14,
    alignItems: "center",
    justifyContent: "center",
  },
  moduleSymbol: {
    fontSize: 22,
    fontWeight: "800",
  },
  moduleNumber: {
    color: "#A1ADA4",
    fontSize: 10,
    fontWeight: "700",
  },
  moduleTitle: {
    color: C.ink,
    fontSize: 16,
    fontWeight: "800",
    lineHeight: 22,
    letterSpacing: -0.3,
    marginBottom: 10,
  },
  moduleDescription: {
    color: C.muted,
    fontSize: 11,
    lineHeight: 18,
    marginBottom: 16,
  },
  moduleBottom: {
    marginTop: "auto",
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 6,
    borderTopWidth: 1,
    borderTopColor: C.border,
    paddingTop: 12,
  },
  moduleAction: {
    flex: 1,
    fontSize: 10,
    fontWeight: "800",
  },
  moduleArrow: {
    fontSize: 19,
  },
  resumeTag: {
    backgroundColor: C.mint,
    borderRadius: 7,
    padding: 7,
    marginTop: 10,
  },
  resumeTagText: {
    color: C.green,
    fontSize: 9,
    fontWeight: "700",
  },
  noteCard: {
    flexDirection: "row",
    gap: 12,
    padding: 17,
    backgroundColor: C.mint,
    borderRadius: 17,
    marginBottom: 27,
  },
  noteIcon: {
    width: 26,
    height: 26,
    borderRadius: 9,
    backgroundColor: C.mint,
    alignItems: "center",
    justifyContent: "center",
  },
  noteIconText: {
    color: C.green,
    fontSize: 15,
    fontWeight: "800",
  },
  noteTitle: {
    color: C.forest,
    fontSize: 12,
    fontWeight: "800",
    lineHeight: 18,
    marginBottom: 5,
  },
  noteDescription: {
    color: C.muted,
    fontSize: 11,
    lineHeight: 18,
  },
  historyCard: {
    flexDirection: "row",
    alignItems: "center",
    gap: 13,
    backgroundColor: C.white,
    borderWidth: 1,
    borderColor: C.border,
    borderRadius: 18,
    padding: 17,
    marginBottom: 16,
  },
  historyIcon: {
    width: 39,
    height: 39,
    borderRadius: 12,
    backgroundColor: C.mint,
    alignItems: "center",
    justifyContent: "center",
  },
  historyIconText: {
    color: C.green,
    fontSize: 25,
    fontWeight: "700",
  },
  historyTitle: {
    color: C.ink,
    fontSize: 13,
    fontWeight: "800",
    marginBottom: 5,
  },
  historyDescription: {
    color: C.muted,
    fontSize: 11,
    lineHeight: 17,
  },
  historyArrow: {
    color: C.green,
    fontSize: 22,
  },
  connectionCard: {
    borderRadius: 18,
    borderWidth: 1,
    borderColor: C.border,
    backgroundColor: C.white,
    padding: 17,
    marginBottom: 5,
  },
  connectionHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    gap: 10,
    flexWrap: "wrap",
    marginBottom: 11,
  },
  connectionTitle: {
    color: C.ink,
    fontSize: 12,
    fontWeight: "800",
  },
  statusPill: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    paddingHorizontal: 9,
    paddingVertical: 6,
    borderRadius: 8,
  },
  statusDot: {
    width: 5,
    height: 5,
    borderRadius: 3,
  },
  statusText: {
    fontSize: 9,
    fontWeight: "700",
  },
  connectionDescription: {
    color: C.muted,
    fontSize: 11,
    lineHeight: 18,
  },
  button: {
    minHeight: 48,
    backgroundColor: C.green,
    borderRadius: 12,
    padding: 14,
    marginTop: 15,
    alignItems: "center",
    justifyContent: "center",
  },
  secondaryButton: {
    backgroundColor: C.mint,
    borderWidth: 1,
    borderColor: C.mintBorder,
  },
  buttonText: {
    color: C.white,
    fontSize: 12,
    fontWeight: "800",
    textAlign: "center",
  },
  modal: {
    flex: 1,
    backgroundColor: C.background,
  },
  modalContent: {
    padding: 23,
    paddingBottom: 35,
  },
  backButton: {
    alignSelf: "flex-start",
    paddingVertical: 12,
    paddingRight: 20,
    marginBottom: 20,
  },
  backButtonText: {
    color: C.green,
    fontSize: 12,
    fontWeight: "800",
  },
  largeModuleIcon: {
    width: 69,
    height: 69,
    borderRadius: 22,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 23,
  },
  largeModuleSymbol: {
    fontSize: 31,
    fontWeight: "800",
  },
  modalTitle: {
    color: C.ink,
    fontSize: 30,
    lineHeight: 38,
    fontWeight: "800",
    letterSpacing: -0.8,
    marginTop: 4,
    marginBottom: 12,
  },
  modalHeading: {
    color: C.muted,
    fontSize: 14,
    lineHeight: 23,
    marginBottom: 24,
  },
  integrationNotice: {
    backgroundColor: C.mint,
    borderWidth: 1,
    borderColor: C.border,
    borderRadius: 17,
    padding: 17,
    marginBottom: 27,
  },
  integrationTitle: {
    color: C.forest,
    fontSize: 13,
    fontWeight: "800",
    marginBottom: 8,
  },
  integrationDescription: {
    color: C.muted,
    fontSize: 12,
    lineHeight: 21,
  },
  overviewCard: {
    flexDirection: "row",
    gap: 13,
    backgroundColor: C.white,
    borderWidth: 1,
    borderColor: C.border,
    borderRadius: 17,
    padding: 17,
    marginTop: 13,
  },
  overviewNumber: {
    width: 29,
    height: 29,
    borderRadius: 10,
    backgroundColor: C.mint,
    alignItems: "center",
    justifyContent: "center",
  },
  overviewNumberText: {
    color: C.green,
    fontSize: 11,
    fontWeight: "800",
  },
  overviewTitle: {
    color: C.ink,
    fontSize: 13,
    fontWeight: "800",
    marginBottom: 6,
  },
  overviewText: {
    color: C.muted,
    fontSize: 12,
    lineHeight: 20,
  },
});
}
