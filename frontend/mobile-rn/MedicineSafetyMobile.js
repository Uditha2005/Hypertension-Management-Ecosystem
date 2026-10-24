import React, {
  useCallback, useEffect, useRef, useState,
} from "react";
import {
  AppState, Image, Modal, Pressable, ScrollView,
  StyleSheet, Text, View,
} from "react-native";
import Ionicons from "@expo/vector-icons/Ionicons";
import {
  setAudioModeAsync, useAudioPlayer, useAudioPlayerStatus,
} from "expo-audio";
import { useAppTheme } from "./CareAccount";

function reviewAlert(result) {
  if (!result) return null;

  const differences = [];
  const warnings = [];

  if (Array.isArray(result.rows)) {
    result.rows.forEach((row) => {
      if (
        !Number.isInteger(row.expected) ||
        !Number.isInteger(row.found) ||
        row.expected === row.found
      ) return;

      differences.push(
        `${row.medicineName || row.productId || "Medicine"}: ` +
        `${row.expected} expected, ${row.found} counted predictions.`
      );
    });
  }

  if (
    result.comparisonType === "total-count" &&
    Number.isInteger(result.expectedTotal) &&
    Number.isInteger(result.detectedTotal) &&
    result.expectedTotal !== result.detectedTotal
  ) {
    differences.push(
      `${result.expectedTotal} pills expected; ` +
      `${result.detectedTotal} detected. Identities were not checked.`
    );
  }

  const uncertain = Array.isArray(result.uncertain)
    ? result.uncertain.length
    : 0;

  if (uncertain) {
    warnings.push(
      `${uncertain} detection(s) have an uncertain or unsupported identity.`
    );
  }

  if (!differences.length && !warnings.length) return null;

  return {
    tone: differences.length ? "red" : "yellow",
    title: differences.length
      ? "Comparison mismatch"
      : "Medicine review needed",
    details: [...differences, ...warnings],
  };
}

export function MedicineCareHeader({ muted, onToggleMute }) {
  const { colors: C, isDark } = useAppTheme();

  return (
    <View style={[
      styles.hero,
      {
        backgroundColor: isDark ? C.mint : "#E1EDE0",
        borderColor: C.border,
      },
    ]}>
      <Image
        source={require("./assets/medicine-care.png")}
        style={styles.heroPhoto}
        resizeMode="cover"
        accessibilityLabel="Illustrative medicine preparation photograph"
      />
      <View style={styles.heroCopy}>
        <Text style={[styles.eyebrow, { color: C.green }]}>
          CARE BEFORE EVERY DOSE
        </Text>
        <Text style={[styles.heroTitle, { color: C.ink }]}>
          A careful check.{"\n"}Before every dose.
        </Text>
        <Text style={[styles.body, { color: C.muted }]}>
          Check the prescription, prepared medicines and quantities.
          AI predictions support your review; they do not confirm identity.
        </Text>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={muted ? "Unmute alerts" : "Mute alerts"}
          onPress={onToggleMute}
          style={[
            styles.soundButton,
            { backgroundColor: C.white, borderColor: C.border },
          ]}
        >
          <Ionicons
            name={muted ? "volume-mute-outline" : "volume-high-outline"}
            size={18}
            color={C.green}
          />
          <Text style={{ color: C.ink, fontWeight: "600" }}>
            {muted ? "Sound off - unmute" : "Sound on - mute"}
          </Text>
        </Pressable>
      </View>
    </View>
  );
}

export default function MedicineSafetyMobile({
  result, eventNumber, active, muted, onMute,
}) {
  const { colors: C } = useAppTheme();
  const redPlayer = useAudioPlayer(require("./assets/warning_msg.mp3"));
  const yellowPlayer = useAudioPlayer(require("./assets/alarm.mp3"));
  const redStatus = useAudioPlayerStatus(redPlayer);
  const yellowStatus = useAudioPlayerStatus(yellowPlayer);

  const [dialog, setDialog] = useState(null);
  const [pending, setPending] = useState(null);
  const [audioMessage, setAudioMessage] = useState("");

  const handled = useRef(0);
  const started = useRef(0);
  const generation = useRef(0);
  const timeout = useRef(null);
  const currentEvent = useRef(eventNumber);
  currentEvent.current = eventNumber;

  const stop = useCallback(() => {
    generation.current += 1;
    if (timeout.current !== null) {
      clearTimeout(timeout.current);
      timeout.current = null;
    }
    redPlayer.pause();
    yellowPlayer.pause();
  }, [redPlayer, yellowPlayer]);

  useEffect(() => {
    return () => stop();
  }, [stop]);

  useEffect(() => {
    const subscription = AppState.addEventListener("change", (state) => {
      if (state !== "active") {
        stop();
        setPending(null);
      }
    });
    return () => subscription.remove();
  }, [stop]);

  useEffect(() => {
    if (!active || muted) {
      stop();
      setPending(null);
    }
    if (!active) setDialog(null);
  }, [active, muted, stop]);

  useEffect(() => {
    if (!eventNumber || handled.current === eventNumber) return;

    handled.current = eventNumber;
    stop();
    setPending(null);
    setAudioMessage("");

    const next = reviewAlert(result);
    setDialog(active ? next : null);

    if (next && active && !muted) {
      setPending({ ...next, eventNumber });
    }
  }, [eventNumber, result, active, muted, stop]);

  useEffect(() => {
    if (!pending || muted || !active) return;

    const player = pending.tone === "red" ? redPlayer : yellowPlayer;
    const status = pending.tone === "red" ? redStatus : yellowStatus;

    if (status.error) {
      setAudioMessage("Sound unavailable. Review the visual alert.");
      setPending(null);
      return;
    }

    if (!status.isLoaded || started.current === pending.eventNumber) return;
    started.current = pending.eventNumber;

    const ticket = generation.current;
    const thisEvent = pending.eventNumber;
    let cancelled = false;

    async function play() {
      try {
        await setAudioModeAsync({
          playsInSilentMode: true,
          shouldPlayInBackground: false,
        });
        await player.seekTo(0);

        if (
          cancelled ||
          ticket !== generation.current ||
          currentEvent.current !== thisEvent
        ) return;

        player.volume = 0.85;
        player.loop = false;
        player.play();

        timeout.current = setTimeout(
          () => {
            if (ticket === generation.current) player.pause();
            timeout.current = null;
          },
          pending.tone === "red" ? 1100 : 2000
        );
      } catch {
        if (!cancelled) {
          setAudioMessage("Sound unavailable. Review the visual alert.");
        }
      }
    }

    play();

    return () => {
      cancelled = true;
    };
  }, [
    pending, muted, active, redPlayer, yellowPlayer,
    redStatus.isLoaded, redStatus.error,
    yellowStatus.isLoaded, yellowStatus.error,
  ]);

  function dismiss() {
    stop();
    setPending(null);
    setDialog(null);
  }

  const red = dialog?.tone === "red";
  const accent = red ? "#CF242A" : "#A97800";

  return (
    <Modal
      visible={Boolean(dialog)}
      transparent
      animationType="fade"
      onRequestClose={dismiss}
      statusBarTranslucent
    >
      <View style={styles.backdrop}>
        <View
          accessibilityViewIsModal
          style={[
            styles.dialog,
            { backgroundColor: C.white, borderTopColor: accent },
          ]}
        >
          <ScrollView contentContainerStyle={styles.dialogContent}>
            <View style={styles.symbol}>
              <Ionicons
                name="warning"
                size={76}
                color={red ? "#D71920" : "#E8B500"}
              />
            </View>

            <Text style={[styles.dialogTitle, { color: accent }]}>
              {dialog?.title}
            </Text>
            <Text style={[styles.body, { color: C.muted, textAlign: "center" }]}>
              Check the tray against the reviewed prescription and packaging.
            </Text>

            <View style={[
              styles.detailBox,
              { backgroundColor: red ? "#FFF0EE" : "#FFF6D6" },
            ]}>
              {(dialog?.details || []).map((detail, index) => (
                <Text
                  key={index}
                  style={[
                    styles.detail,
                    { color: red ? "#982822" : "#705000" },
                  ]}
                >
                  {"\u2022"} {detail}
                </Text>
              ))}
            </View>

            <Text style={[styles.disclaimer, { color: C.muted }]}>
              These are model predictions, not confirmed medicine identities.
              Repeated tablets may be prescribed. This alert does not recommend
              changing a dose.
            </Text>

            {!!audioMessage && (
              <Text
                accessibilityLiveRegion="polite"
                style={[styles.disclaimer, { color: C.muted }]}
              >
                {audioMessage}
              </Text>
            )}

            {!muted && (
              <Pressable
                accessibilityRole="button"
                onPress={() => { stop(); onMute(); }}
                style={[styles.secondary, { borderColor: C.border }]}
              >
                <Text style={{ color: C.ink, fontWeight: "600" }}>
                  Mute sound
                </Text>
              </Pressable>
            )}

            <Pressable
              accessibilityRole="button"
              onPress={dismiss}
              style={[styles.close, { backgroundColor: C.green }]}
            >
              <Text style={styles.closeText}>Close and review results</Text>
            </Pressable>
          </ScrollView>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  hero: {
    borderWidth: 1, borderRadius: 22,
    overflow: "hidden", marginBottom: 22,
  },
  heroPhoto: { width: "100%", height: 170 },
  heroCopy: { padding: 20 },
  eyebrow: { fontSize: 10, fontWeight: "800", letterSpacing: 1.3 },
  heroTitle: {
    fontSize: 27, lineHeight: 33,
    fontWeight: "800", marginVertical: 12,
  },
  body: { fontSize: 13, lineHeight: 21 },
  soundButton: {
    flexDirection: "row", alignItems: "center", gap: 8,
    alignSelf: "flex-start", marginTop: 16,
    paddingVertical: 10, paddingHorizontal: 13,
    borderWidth: 1, borderRadius: 10,
  },
  backdrop: {
    flex: 1, backgroundColor: "rgba(10,25,17,0.6)",
    justifyContent: "center", padding: 22,
  },
  dialog: {
    maxHeight: "85%", borderRadius: 22,
    borderTopWidth: 7, overflow: "hidden",
  },
  dialogContent: { padding: 23 },
  symbol: { alignItems: "center", marginBottom: 12 },
  dialogTitle: {
    fontSize: 23, fontWeight: "800",
    textAlign: "center", marginBottom: 12,
  },
  detailBox: { padding: 15, borderRadius: 12, marginVertical: 18 },
  detail: { fontSize: 13, lineHeight: 21, marginBottom: 8 },
  disclaimer: { fontSize: 11, lineHeight: 18, marginBottom: 15 },
  secondary: {
    borderWidth: 1, padding: 13, borderRadius: 11,
    alignItems: "center", marginBottom: 10,
  },
  close: { padding: 15, borderRadius: 11, alignItems: "center" },
  closeText: { color: "#FFFFFF", fontWeight: "700", fontSize: 13 },
});
