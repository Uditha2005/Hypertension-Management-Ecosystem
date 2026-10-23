import Ionicons from "@expo/vector-icons/Ionicons";
import { CareProviders, AuthGate, SettingsContent, useAppTheme } from "./CareAccount";
import HomeScreen from "./HomeScreen";
import React, { useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  BackHandler,
  Image,
  KeyboardAvoidingView,
  Linking,
  Modal,
  Platform,
  Pressable,
  ScrollView,
  StatusBar,
  StyleSheet,
  Switch,
  Text,
  TextInput,
  View,
} from "react-native";
import {
  SafeAreaProvider,
  SafeAreaView,
} from "react-native-safe-area-context";
import * as ImagePicker from "expo-image-picker";
import {
  ImageManipulator,
  SaveFormat,
} from "expo-image-manipulator";
import AsyncStorage from "@react-native-async-storage/async-storage";

const LOGO = require("./assets/hypercare-icon.png");
const API_STORAGE = "hypercare-api-url";
const DEFAULT_API = "http://192.168.8.151:8000";
const PREFIX = "/api/medicine";

const C = {
  bg: "#F2F5F2",
  white: "#FFFFFF",
  green: "#187E63",
  forest: "#123F35",
  mint: "#E5F2E9",
  mintBorder: "#C9DFD0",
  ink: "#20372D",
  muted: "#718077",
  border: "#DEE6DF",
  amber: "#8C641B",
  amberBg: "#FFF3DA",
  red: "#AC3D3D",
  redBg: "#FBEAEA",
};

const PALETTE = {
  green: { bg: C.mint, ink: C.green },
  amber: { bg: C.amberBg, ink: C.amber },
  red: { bg: C.redBg, ink: C.red },
  grey: { bg: "#EEF1EE", ink: C.muted },
};

function emptyReview() {
  return {
    step: 1,
    rxPhoto: null,
    text: "",
    rows: [],
    reference: "",
    extraction: "",
    reviewed: false,
    saved: null,
    trayPhoto: null,
    result: null,
  };
}

function identity(value) {
  return String(value || "")
    .normalize("NFKC")
    .toLowerCase()
    .replace(/[µμ]/g, "u")
    .replace(/_/g, " ")
    .replace(/\b(?:film|coated|tablets?|tabs?|capsules?|caps?)\b/g, "")
    .replace(/[^a-z0-9%]/g, "");
}

function strengthKey(value) {
  return String(value || "")
    .toLowerCase()
    .replace(/[µμ]/g, "u")
    .replace(/ug/g, "mcg")
    .replace(/\s/g, "");
}

function matchProduct(row, products) {
  const existing = products.find((p) => p.id === row.productId);
  if (existing) return existing.id;

  if (!row.medicineName || !row.strength) return "";

  const matches = products.filter((product) => {
    if (
      !product.strength ||
      strengthKey(product.strength) !== strengthKey(row.strength)
    ) {
      return false;
    }

    const name = String(product.name || "")
      .replace(/_/g, " ")
      .replace(/\d+(?:\.\d+)?\s*(?:mcg|ug|mg|g|ml|iu)\b/gi, "");

    return identity(name) === identity(row.medicineName);
  });

  return matches.length === 1 ? matches[0].id : "";
}

function quantityValid(value) {
  const text = String(value ?? "").trim();
  return /^\d+$/.test(text) && Number(text) >= 1 && Number(text) <= 100;
}

function dateLabel(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "" : date.toLocaleString();
}

function comparisonTone(result) {
  if ((result.uncertain || []).length) return "amber";
  return (result.rows || []).some((row) => row.difference !== 0)
    ? "red"
    : "green";
}

function comparisonRowTone(row, result) {
  if (row.difference > 0) return "red";

  const related = (result.uncertain || []).some(
    (detection) =>
      detection.label === row.productId ||
      detection.productId === row.productId ||
      (detection.alternatives || []).some(
        (alternative) => alternative.label === row.productId
      )
  );

  if (related) return "amber";
  return row.difference === 0 ? "green" : "red";
}

function Tag({ text, tone = "green" }) {
  const { colors: C, isDark } = useAppTheme();
  const s = React.useMemo(() => makeStyles(C), [C]);
  const PALETTE = {
    green: { bg: C.mint, ink: C.green },
    amber: { bg: C.amberBg, ink: C.amber },
    red: { bg: C.redBg, ink: C.red },
    grey: { bg: C.bg, ink: C.muted },
  };

  const color = PALETTE[tone] || PALETTE.grey;

  return (
    <View style={[s.tag, { backgroundColor: color.bg }]}>
      <Text style={[s.tagText, { color: color.ink }]}>{text}</Text>
    </View>
  );
}

function Action({
  title,
  onPress,
  secondary = false,
  disabled = false,
}) {
  const { colors: C, isDark } = useAppTheme();
  const s = React.useMemo(() => makeStyles(C), [C]);
  const PALETTE = {
    green: { bg: C.mint, ink: C.green },
    amber: { bg: C.amberBg, ink: C.amber },
    red: { bg: C.redBg, ink: C.red },
    grey: { bg: C.bg, ink: C.muted },
  };

  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ disabled }}
      disabled={disabled}
      onPress={onPress}
      style={({ pressed }) => [
        s.action,
        secondary && s.actionSecondary,
        disabled && { opacity: 0.45 },
        pressed && { opacity: 0.75 },
      ]}
    >
      <Text style={[s.actionText, secondary && { color: C.green }]}>
        {title}
      </Text>
    </Pressable>
  );
}

function Input({ label, style, multiline, ...props }) {
  const { colors: C, isDark } = useAppTheme();
  const s = React.useMemo(() => makeStyles(C), [C]);
  const PALETTE = {
    green: { bg: C.mint, ink: C.green },
    amber: { bg: C.amberBg, ink: C.amber },
    red: { bg: C.redBg, ink: C.red },
    grey: { bg: C.bg, ink: C.muted },
  };

  return (
    <View style={[s.inputGroup, style]}>
      <Text style={s.label}>{label}</Text>
      <TextInput
        {...props}
        multiline={multiline}
        placeholderTextColor="#99A39C"
        style={[s.input, multiline && s.multiline]}
      />
    </View>
  );
}

function Panel({ children, style }) {
  const { colors: C, isDark } = useAppTheme();
  const s = React.useMemo(() => makeStyles(C), [C]);
  const PALETTE = {
    green: { bg: C.mint, ink: C.green },
    amber: { bg: C.amberBg, ink: C.amber },
    red: { bg: C.redBg, ink: C.red },
    grey: { bg: C.bg, ink: C.muted },
  };

  return <View style={[s.panel, style]}>{children}</View>;
}

function PhotoUpload({ title, photo, onChoose, onCamera, disabled }) {
  const { colors: C, isDark } = useAppTheme();
  const s = React.useMemo(() => makeStyles(C), [C]);
  const PALETTE = {
    green: { bg: C.mint, ink: C.green },
    amber: { bg: C.amberBg, ink: C.amber },
    red: { bg: C.redBg, ink: C.red },
    grey: { bg: C.bg, ink: C.muted },
  };

  return (
    <Panel>
      <Text style={s.panelTitle}>{title}</Text>

      <Pressable
        accessibilityRole="button"
        accessibilityLabel={`Choose ${title.toLowerCase()}`}
        disabled={disabled}
        onPress={onChoose}
        style={({ pressed }) => [
          s.upload,
          pressed && { opacity: 0.75 },
          disabled && { opacity: 0.6 },
        ]}
      >
        {photo ? (
          <>
            <Image
              source={{ uri: photo.uri }}
              style={s.uploadPhoto}
              resizeMode="contain"
            />
            <View style={s.changePhoto}>
              <Text style={s.changePhotoText}>Tap to change photo</Text>
            </View>
          </>
        ) : (
          <>
            <View style={s.uploadSymbol}>
              <Text style={s.uploadPlus}>＋</Text>
            </View>
            <Text style={s.uploadTitle}>Tap to add a photo</Text>
            <Text style={s.uploadHint}>
              Choose from your gallery or use the camera.
            </Text>
          </>
        )}
      </Pressable>

      <View style={s.columns}>
        <View style={s.flex}>
          <Action
            title="Take photo"
            secondary
            disabled={disabled}
            onPress={onCamera}
          />
        </View>
        <View style={s.flex}>
          <Action
            title="Choose photo"
            secondary
            disabled={disabled}
            onPress={onChoose}
          />
        </View>
      </View>
    </Panel>
  );
}

function Results({ result }) {
  const { colors: C, isDark } = useAppTheme();
  const s = React.useMemo(() => makeStyles(C), [C]);
  const PALETTE = {
    green: { bg: C.mint, ink: C.green },
    amber: { bg: C.amberBg, ink: C.amber },
    red: { bg: C.redBg, ink: C.red },
    grey: { bg: C.bg, ink: C.muted },
  };

  const rows = result.rows || [];
  const uncertain = result.uncertain || [];
  const recognition = result.recognition;
  const threshold = result.confidenceThreshold ?? 0.65;
  const tone = comparisonTone(result);
  const expected = rows.reduce((total, row) => total + row.expected, 0);
  const found = rows.reduce((total, row) => total + row.found, 0);

  return (
    <>
      <Panel>
        <Text style={s.eyebrow}>COMPARISON SUMMARY</Text>
        <Text style={s.panelTitle}>Tray review results</Text>

        <Tag
          text={result.status || "Review required"}
          tone={tone}
        />

        <View style={s.metrics}>
          {[
            [expected, "Expected"],
            [found, "Counted"],
            [uncertain.length, "Uncertain"],
          ].map(([number, label]) => (
            <View key={label} style={s.metric}>
              <Text style={s.metricNumber}>{number}</Text>
              <Text style={s.caption}>{label}</Text>
            </View>
          ))}
        </View>

        <Text style={s.body}>
          Model predictions are compared with your reviewed medicine list.
          Uncertain detections are excluded from product counts.
        </Text>
      </Panel>

      {rows.map((row) => {
        const rowTone = comparisonRowTone(row, result);
        const color = PALETTE[rowTone];
        const message =
          rowTone === "amber"
            ? "Uncertain detection — review"
            : row.difference === 0
              ? "Counts match — review"
              : row.difference > 0
                ? `${row.difference} extra predicted`
                : `${Math.abs(row.difference)} fewer predicted`;

        return (
          <Panel
            key={row.productId}
            style={{ borderLeftWidth: 4, borderLeftColor: color.ink }}
          >
            <Text style={s.medicineTitle}>{row.medicineName}</Text>
            <Text style={s.caption}>{row.productId}</Text>

            {!!row.strength && (
              <Text style={[s.caption, { marginTop: 5 }]}>
                Recorded strength: {row.strength} · not verified
              </Text>
            )}

            <View style={s.countLine}>
              <Text style={s.countText}>Expected {row.expected}</Text>
              <Text style={s.countText}>Counted {row.found}</Text>
            </View>

            <Tag text={message} tone={rowTone} />
          </Panel>
        );
      })}

      {!!uncertain.length && (
        <Panel style={{ backgroundColor: C.amberBg, borderColor: "#EDDFB9" }}>
          <Text style={[s.panelTitle, { color: C.amber }]}>
            Uncertain detections
          </Text>
          {uncertain.map((item, index) => (
            <View key={index} style={{ marginBottom: 13 }}>
              <Text style={[s.rowTitle, { color: C.amber }]}>
                {item.productName || item.label || "Unidentified medicine"}
              </Text>
              <Text style={[s.caption, { color: C.amber }]}>
                Model score: {(Number(item.confidence) * 100).toFixed(1)}%
                {"\n"}
                {item.reason || "Requires review"}
              </Text>
            </View>
          ))}
        </Panel>
      )}

      {recognition && (
        <Panel>
          <Text style={s.eyebrow}>MODEL OUTPUT</Text>
          <Text style={s.panelTitle}>Photo predictions</Text>

          {!!recognition.annotatedImage && (
            <Image
              source={{ uri: recognition.annotatedImage }}
              style={s.annotatedPhoto}
              resizeMode="contain"
            />
          )}

          {(recognition.detections || []).map((item, index) => {
            const uncertainPrediction =
              item.unmapped ||
              item.identityUncertain ||
              item.confidence < threshold;

            return (
              <View key={index} style={s.prediction}>
                <View style={s.flex}>
                  <Text style={s.rowTitle}>
                    {item.productName || item.label}
                  </Text>
                  <Text style={s.caption}>
                    {uncertainPrediction
                      ? "Uncertain · excluded from counts"
                      : "Predicted identity"}
                  </Text>
                </View>
                <Tag
                  text={`${(item.confidence * 100).toFixed(1)}%`}
                  tone={uncertainPrediction ? "amber" : "green"}
                />
              </View>
            );
          })}
        </Panel>
      )}

      <Text style={s.disclaimer}>
        Matching counts do not confirm medicine identity, strength, timing or
        clinical suitability. Model scores are not correctness guarantees.
        Check the original prescription and actual medicines.
      </Text>
    </>
  );
}

export default function App() {
  return (
    <SafeAreaProvider>
      <CareProviders>
        <AuthGate>
          <HyperCare />
        </AuthGate>
      </CareProviders>
    </SafeAreaProvider>
  );
}

function HyperCare() {
  const { colors: C, isDark } = useAppTheme();
  const s = React.useMemo(() => makeStyles(C), [C]);
  const PALETTE = {
    green: { bg: C.mint, ink: C.green },
    amber: { bg: C.amberBg, ink: C.amber },
    red: { bg: C.redBg, ink: C.red },
    grey: { bg: C.bg, ink: C.muted },
  };

  const [tab, setTab] = useState("home");
  const [flow, setFlow] = useState(emptyReview);
  const [apiUrl, setApiUrl] = useState(DEFAULT_API);
  const [draftUrl, setDraftUrl] = useState(DEFAULT_API);
  const [bootstrap, setBootstrap] = useState(null);
  const [connection, setConnection] = useState("Not connected");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [useLLM, setUseLLM] = useState(true);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [productRow, setProductRow] = useState(null);
  const [productSearch, setProductSearch] = useState("");
  const [history, setHistory] = useState([]);
  const [historyLoaded, setHistoryLoaded] = useState(false);
  const [historySearch, setHistorySearch] = useState("");
  const [historyDetail, setHistoryDetail] = useState(null);

  const mounted = useRef(true);
  const lock = useRef(false);
  const activeRequest = useRef(null);
  const scroll = useRef(null);

  const products = bootstrap?.products || [];
  const working = Boolean(busy);
  const hasReview =
    Boolean(flow.rxPhoto) || Boolean(flow.text.trim()) || Boolean(flow.rows.length);

  useEffect(() => {
    mounted.current = true;

    async function initialize() {
      let base = DEFAULT_API;

      try {
        base = (await AsyncStorage.getItem(API_STORAGE)) || DEFAULT_API;
      } catch {
        // Use the editable default when local settings cannot be read.
      }

      if (!mounted.current) return;

      setApiUrl(base);
      setDraftUrl(base);
      connect(base);
    }

    initialize();

    return () => {
      mounted.current = false;
      activeRequest.current?.abort();
    };
  }, []);

  useEffect(() => {
    scroll.current?.scrollTo({ y: 0, animated: true });
  }, [tab, flow.step, historyDetail]);

  useEffect(() => {
    const subscription = BackHandler.addEventListener(
      "hardwareBackPress",
      () => {
        if (working) return true;

        if (tab === "history" && historyDetail) {
          setHistoryDetail(null);
          return true;
        }

        if (tab === "medicines" && flow.step > 1) {
          setFlow((current) => ({
            ...current,
            step: current.step - 1,
          }));
          setError("");
          return true;
        }

        if (tab !== "home") {
          setTab("home");
          setError("");
          return true;
        }

        if (hasReview && !flow.result) {
          Alert.alert(
            "Leave HyperCare?",
            "Your unfinished review is kept only while this app session remains open.",
            [
              { text: "Stay", style: "cancel" },
              { text: "Exit", onPress: () => BackHandler.exitApp() },
            ]
          );
          return true;
        }

        return false;
      }
    );

    return () => subscription.remove();
  }, [tab, flow.step, historyDetail, working, hasReview, flow.result]);

  async function run(message, operation) {
    if (lock.current) return;

    lock.current = true;
    setBusy(message);
    setError("");

    try {
      await operation();
    } catch (err) {
      if (mounted.current) {
        setError(err.message || "Something went wrong. Please try again.");
      }
    } finally {
      lock.current = false;
      if (mounted.current) setBusy("");
    }
  }

  async function request(path, payload, base = apiUrl, timeoutMs = 120000) {
    const controller = new AbortController();
    activeRequest.current = controller;
    const timer = setTimeout(() => controller.abort(), timeoutMs);

    try {
      const response = await fetch(`${base}${PREFIX}${path}`, {
        method: payload === undefined ? "GET" : "POST",
        headers: { "Content-Type": "application/json" },
        body: payload === undefined ? undefined : JSON.stringify(payload),
        signal: controller.signal,
      });

      const raw = await response.text();
      let data;

      try {
        data = JSON.parse(raw);
      } catch {
        throw new Error("The API returned an unexpected response.");
      }

      if (!response.ok) {
        throw new Error(
          typeof data.error === "string"
            ? data.error
            : typeof data.detail === "string"
              ? data.detail
              : `Request failed: HTTP ${response.status}`
        );
      }

      if (!mounted.current) throw new Error("App closed.");
      return data;
    } catch (err) {
      if (err.name === "AbortError") {
        throw new Error(
          "The request timed out. Check your laptop API terminal and try again."
        );
      }

      if (
        String(err.message).includes("Network request failed") ||
        String(err.message).includes("Failed to fetch")
      ) {
        throw new Error(
          "Cannot reach the medicine API. Check the laptop IP address, Wi-Fi and port 8000."
        );
      }

      throw err;
    } finally {
      clearTimeout(timer);
      if (activeRequest.current === controller) activeRequest.current = null;
    }
  }

  async function loadBootstrap(base) {
    setConnection("Connecting");
    setBootstrap(null);

    try {
      const data = await request("/bootstrap", undefined, base, 20000);

      if (!data?.modelReady || !Array.isArray(data.products)) {
        throw new Error("The medicine model is not ready.");
      }

      setBootstrap(data);
      setConnection("Connected");
    } catch (err) {
      if (mounted.current) setConnection("Not connected");
      throw err;
    }
  }

  function connect(base = apiUrl) {
    return run("Connecting to medicine service…", () => loadBootstrap(base));
  }

  function editFlow(changes) {
    setFlow((current) => ({
      ...current,
      ...changes,
      reviewed: false,
      saved: null,
      result: null,
    }));
  }

  function editRow(key, field, value) {
    setFlow((current) => ({
      ...current,
      reviewed: false,
      saved: null,
      result: null,
      rows: current.rows.map((row) => {
        if (row.key !== key) return row;

        const changed = { ...row, [field]: value };

        if (field === "medicineName" || field === "strength") {
          changed.productId = matchProduct(
            { ...changed, productId: "" },
            products
          );
        }

        return changed;
      }),
    }));
  }

  function resetReview() {
    const reset = () => {
      setFlow(emptyReview());
      setTab("medicines");
      setError("");
    };

    if (!hasReview) {
      reset();
      return;
    }

    Alert.alert(
      "Start a new review?",
      "The current photo and unfinished changes will be cleared. Saved comparisons remain in History.",
      [
        { text: "Keep current", style: "cancel" },
        { text: "Start new", onPress: reset },
      ]
    );
  }

  async function pickPhoto(kind, camera) {
    await run("Preparing photo…", async () => {
      if (camera) {
        const permission = await ImagePicker.requestCameraPermissionsAsync();

        if (!permission.granted) {
          Alert.alert(
            "Camera access needed",
            "Allow HyperCare or Expo Go to use the camera in phone settings.",
            [
              { text: "Cancel", style: "cancel" },
              { text: "Open settings", onPress: () => Linking.openSettings() },
            ]
          );
          return;
        }
      }

      const options = {
        mediaTypes: ["images"],
        allowsEditing: false,
        quality: 1,
      };

      const selection = camera
        ? await ImagePicker.launchCameraAsync(options)
        : await ImagePicker.launchImageLibraryAsync(options);

      if (selection.canceled || !selection.assets?.length) return;

      const asset = selection.assets[0];
      const context = ImageManipulator.manipulate(asset.uri);
      const limit = kind === "rx" ? 2200 : 1920;

      if (Math.max(asset.width, asset.height) > limit) {
        context.resize(
          asset.width >= asset.height
            ? { width: limit }
            : { height: limit }
        );
      }

      const rendered = await context.renderAsync();
      const prepared = await rendered.saveAsync({
        format: SaveFormat.JPEG,
        compress: 0.9,
        base64: true,
      });

      if (!prepared.base64) throw new Error("Could not prepare this photo.");

      if (prepared.base64.length > 6900000) {
        throw new Error("This photo is too large. Select a smaller image.");
      }

      const photo = {
        uri: prepared.uri,
        imageData: `data:image/jpeg;base64,${prepared.base64}`,
      };

      if (kind === "rx") {
        setFlow((current) => ({
          ...emptyReview(),
          reference: current.reference,
          rxPhoto: photo,
        }));
      } else {
        setFlow((current) => ({
          ...current,
          trayPhoto: photo,
          result: null,
        }));
      }
    });
  }

  function choosePhoto(kind, camera = false) {
    if (working) return;

    if (kind === "rx" && (flow.text.trim() || flow.rows.length)) {
      Alert.alert(
        "Replace prescription?",
        "The extracted text and current medicine review will be cleared.",
        [
          { text: "Cancel", style: "cancel" },
          {
            text: "Replace",
            onPress: () => pickPhoto(kind, camera),
          },
        ]
      );
      return;
    }

    pickPhoto(kind, camera);
  }

  async function extractPrescription() {
    await run("Reading prescription instructions…", async () => {
      let source = flow.text.trim();

      if (!source) {
        if (!flow.rxPhoto) {
          throw new Error("Add a prescription photo or enter its text.");
        }

        const ocr = await request("/prescription/ocr", {
          imageData: flow.rxPhoto.imageData,
        });

        if (typeof ocr.text !== "string" || !ocr.text.trim()) {
          throw new Error(
            "No text was found. Use a clearer photo or enter the text below."
          );
        }

        source = ocr.text.trim();
        setFlow((current) => ({ ...current, text: source }));
      }

      if (source.length > 12000) {
        throw new Error("Use at most 12,000 characters.");
      }

      const draft = await request("/prescription/draft", {
        text: source,
        useLLM,
        trayScope: "single-dose",
      });

      if (
        !Array.isArray(draft.rows) ||
        !draft.rows.length ||
        draft.rows.length > 50
      ) {
        throw new Error(
          "No usable medicine draft was returned. Check the extracted text."
        );
      }

      const rows = draft.rows.map((row, index) => ({
        ...row,
        key: `medicine-${Date.now()}-${index}`,
        medicineName: String(row.medicineName || ""),
        strength: String(row.strength || ""),
        quantity: row.quantity == null ? "" : String(row.quantity),
        productId: matchProduct(row, products),
      }));

      setFlow((current) => ({
        ...current,
        rows,
        step: 2,
        reviewed: false,
        saved: null,
        result: null,
        extraction: [
          draft.provider ? `Source: ${draft.provider}` : "Draft extracted",
          draft.model || "",
        ]
          .filter(Boolean)
          .join(" · "),
      }));
    });
  }

  async function saveReview() {
    await run("Saving reviewed medicine list…", async () => {
      if (!flow.reviewed) {
        throw new Error("Confirm that you reviewed the medicine list.");
      }

      if (!flow.rows.length || flow.rows.length > 50) {
        throw new Error("Use between 1 and 50 medicine rows.");
      }

      const selected = new Set();

      for (const row of flow.rows) {
        if (!row.medicineName.trim()) {
          throw new Error("Every medicine needs a name.");
        }

        if (!quantityValid(row.quantity)) {
          throw new Error(
            `Check the quantity for ${row.medicineName}. Use a whole number from 1 to 100.`
          );
        }

        const product = products.find((p) => p.id === row.productId);

        if (!product) {
          throw new Error(
            `Select the exact trained product for ${row.medicineName}.`
          );
        }

        if (
          row.strength.trim() &&
          product.strength &&
          strengthKey(row.strength) !== strengthKey(product.strength)
        ) {
          throw new Error(
            `The recorded and selected strengths differ for ${row.medicineName}. Check the original.`
          );
        }

        if (selected.has(product.id)) {
          throw new Error(
            "Combine duplicate product rows into one reviewed quantity."
          );
        }

        selected.add(product.id);
      }

      const saved = await request("/prescription/review", {
        reference: flow.reference.trim(),
        doseLabel: "One-dose tray",
        reviewed: true,
        items: flow.rows.map((row) => ({
          medicineName: row.medicineName.trim(),
          strength: row.strength.trim(),
          productId: row.productId,
          quantity: Number(row.quantity),
        })),
      });

      if (!saved?.id) {
        throw new Error("The API did not return a saved prescription ID.");
      }

      setFlow((current) => ({
        ...current,
        saved,
        step: 3,
        result: null,
      }));
    });
  }

  async function compareTray() {
    await run("Detecting medicines and comparing counts…", async () => {
      if (!flow.saved?.id || !flow.trayPhoto) {
        throw new Error("Save the reviewed list and add a tray photo first.");
      }

      const result = await request("/verify-reviewed", {
        prescriptionId: flow.saved.id,
        imageData: flow.trayPhoto.imageData,
      });

      if (
        !Array.isArray(result.rows) ||
        !result.rows.length ||
        !Array.isArray(result.uncertain)
      ) {
        throw new Error("The API returned an unexpected comparison.");
      }

      setFlow((current) => ({ ...current, result }));
      setHistoryLoaded(false);
    });
  }

  async function loadHistory() {
    await run("Loading saved reviews…", async () => {
      const data = await request("/history");

      if (!Array.isArray(data)) {
        throw new Error("The API returned unexpected history data.");
      }

      setHistory(data);
      setHistoryLoaded(true);
    });
  }

  function changeTab(next) {
    if (working) return;
    setError("");
    setTab(next);
    setHistoryDetail(null);

    if (next === "history") loadHistory();
  }

  function openSettings() {
    if (working) return;
    setDraftUrl(apiUrl);
    setSettingsOpen(true);
  }

  async function applySettings(addressOverride) {
    const base = (
      typeof addressOverride === "string" ? addressOverride : draftUrl
    ).trim().replace(/\/+$/, "");

    if (!/^https?:\/\/[^/\s?#]+$/i.test(base)) {
      Alert.alert(
        "Check server address",
        "Use an address such as http://192.168.8.151:8000"
      );
      return;
    }

    const changed = base !== apiUrl;

    const apply = () =>
      run("Saving connection settings…", async () => {
        await AsyncStorage.setItem(API_STORAGE, base);
        setApiUrl(base);

        if (changed) {
          setFlow(emptyReview());
          setHistory([]);
          setHistoryLoaded(false);
          setHistoryDetail(null);
        }

        await loadBootstrap(base);
        setSettingsOpen(false);
      });

    if (changed && hasReview) {
      Alert.alert(
        "Change server?",
        "Changing the server clears the current review because its saved records belong to the previous server.",
        [
          { text: "Cancel", style: "cancel" },
          { text: "Change server", onPress: apply },
        ]
      );
    } else {
      apply();
    }
  }

  function selectProduct(product) {
    const key = productRow;

    Alert.alert(
      "Confirm exact product",
      `Select “${product.name}” for this row? Check the medicine and strength against the original prescription.`,
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Select product",
          onPress: () => {
            editRow(key, "productId", product.id);
            setProductRow(null);
          },
        },
      ]
    );
  }

  const filteredHistory = history.filter((record) =>
    `${record.reference || ""} ${record.status || ""} ${
      record.createdAt || ""
    }`
      .toLowerCase()
      .includes(historySearch.toLowerCase())
  );

  const filteredProducts = products.filter((product) =>
    `${product.name} ${product.strength || ""}`
      .toLowerCase()
      .includes(productSearch.toLowerCase())
  );

  const missingRows = flow.rows.filter(
    (row) => !row.productId || !quantityValid(row.quantity)
  ).length;

  return (
    <SafeAreaView style={s.app} edges={["top", "left", "right", "bottom"]}>
      <StatusBar barStyle={isDark ? "light-content" : "dark-content"} backgroundColor={C.bg} />

      <View style={s.header}>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="Go to Home"
          disabled={working}
          onPress={() => changeTab("home")}
          style={{ padding: 3 }}
        >
          <Image source={LOGO} style={s.logo} />
        </Pressable>
        <View style={s.flex}>
          <Text style={s.brand}>HyperCare</Text>
          <Text style={s.brandCaption}>Tap the logo for Home</Text>
        </View>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="Open connection settings"
          disabled={working}
          onPress={openSettings}
          style={s.settingsButton}
        >
          <Text style={s.settingsText}>Settings</Text>
        </Pressable>
      </View>

      <KeyboardAvoidingView
        style={s.flex}
        behavior={Platform.OS === "ios" ? "padding" : undefined}
      >
        <ScrollView
          ref={scroll}
          keyboardShouldPersistTaps="handled"
          contentContainerStyle={s.content}
        >
          {!!busy && (
            <View
              accessibilityLiveRegion="polite"
              style={s.busyBox}
            >
              <ActivityIndicator color={C.green} />
              <Text style={s.busyText}>{busy}</Text>
            </View>
          )}

          {!!error && (
            <View accessibilityLiveRegion="polite" style={s.errorBox}>
              <Text style={s.errorTitle}>Couldn’t complete this step</Text>
              <Text style={s.errorText}>{error}</Text>
              <Pressable onPress={() => setError("")} style={s.dismiss}>
                <Text style={s.errorTitle}>Dismiss</Text>
              </Pressable>
            </View>
          )}

          {tab === "home" && (
            <HomeScreen
              onOpenMedicine={() => changeTab("medicines")}
              onOpenHistory={() => changeTab("history")}
              onConnect={() => connect()}
              connection={connection}
              modelReady={Boolean(bootstrap)}
              hasReview={hasReview}
              busy={working}
            />
          )}

          {tab === "medicines" && (
            <>
              <View style={s.between}>
                <Text style={s.eyebrow}>MEDICINE VERIFICATION</Text>
                <Tag text="One-dose tray" tone="grey" />
              </View>
              <Text style={s.title}>
                {flow.step === 1
                  ? "Read the prescription."
                  : flow.step === 2
                    ? "Review your list."
                    : "Compare your tray."}
              </Text>
              <Text style={s.subtitle}>
                {flow.step === 1
                  ? "Start with a clear photo or enter prescription text."
                  : flow.step === 2
                    ? "Confirm each medicine, supported product and dose quantity."
                    : "Keep pills separated and clearly visible in the photo."}
              </Text>

              <Pressable
                accessibilityRole="button"
                disabled={working}
                onPress={() => changeTab("history")}
                style={{
                  alignSelf: "flex-start",
                  paddingVertical: 10,
                  marginBottom: 12,
                }}
              >
                <Text style={s.link}>View medicine review history ?</Text>
              </Pressable>

              <View style={s.steps}>
                {["Prescription", "Review", "Tray"].map((label, index) => (
                  <View style={s.stepItem} key={label}>
                    <View
                      style={[
                        s.stepNumber,
                        flow.step >= index + 1 && s.stepActive,
                      ]}
                    >
                      <Text
                        style={[
                          s.stepNumberText,
                          flow.step >= index + 1 && { color: C.white },
                        ]}
                      >
                        {index + 1}
                      </Text>
                    </View>
                    <Text style={s.stepLabel}>{label}</Text>
                  </View>
                ))}
              </View>

              {!bootstrap && (
                <Panel style={{ backgroundColor: C.amberBg }}>
                  <Text style={s.panelTitle}>Connect your medicine service</Text>
                  <Text style={s.body}>
                    Confirm the laptop address in Settings, then retry.
                  </Text>
                  <Action
                    title="Retry connection"
                    disabled={working}
                    onPress={() => connect()}
                  />
                </Panel>
              )}

              {flow.step === 1 && (
                <>
                  <PhotoUpload
                    title="Prescription photo"
                    photo={flow.rxPhoto}
                    disabled={working}
                    onChoose={() => choosePhoto("rx")}
                    onCamera={() => choosePhoto("rx", true)}
                  />

                  <Panel>
                    <Text style={s.panelTitle}>Prescription instructions</Text>
                    <Text style={s.body}>
                      Leave this empty to read the photo. OCR text appears here
                      so you can correct it and extract again.
                    </Text>

                    <Input
                      label="Original text"
                      value={flow.text}
                      placeholder="Prescription instructions…"
                      multiline
                      editable={!working}
                      maxLength={12000}
                      onChangeText={(value) =>
                        editFlow({
                          text: value,
                          rows: [],
                          extraction: "",
                        })
                      }
                    />

                    <View style={[s.between, { marginTop: 20 }]}>
                      <View style={s.flex}>
                        <Text style={s.rowTitle}>LLM extraction</Text>
                        <Text style={s.caption}>
                          {bootstrap?.llmConfigured
                            ? "Groq configured on the laptop"
                            : "Groq is not configured; server fallback may apply"}
                        </Text>
                      </View>
                      <Switch
                        disabled={working}
                        value={useLLM}
                        trackColor={{ false: C.border, true: "#9DCFB1" }}
                        thumbColor={useLLM ? C.green : "#F5F5F5"}
                        onValueChange={(value) => {
                          setUseLLM(value);
                          editFlow({ rows: [], extraction: "" });
                        }}
                      />
                    </View>

                    <View style={s.infoBox}>
                      <Text style={s.caption}>
                        Photos go to your laptop API. With LLM extraction on,
                        prescription text is also sent to Groq. Use
                        de-identified research samples.
                      </Text>
                    </View>

                    <Action
                      title="Extract medicine list"
                      disabled={
                        working ||
                        !bootstrap ||
                        (!flow.rxPhoto && !flow.text.trim())
                      }
                      onPress={extractPrescription}
                    />
                  </Panel>
                </>
              )}

              {flow.step === 2 && (
                <>
                  <Panel>
                    <Text style={s.panelTitle}>Check the original</Text>
                    <Text style={s.body}>
                      Confirm that each medicine belongs to this scheduled
                      dose. Unclear quantities remain blank rather than being
                      guessed.
                    </Text>

                    {!!flow.extraction && (
                      <Text style={[s.caption, { marginTop: 10 }]}>
                        {flow.extraction}
                      </Text>
                    )}

                    <Input
                      label="Review reference · optional"
                      value={flow.reference}
                      placeholder="Example: Research tray 01"
                      maxLength={200}
                      editable={!working}
                      onChangeText={(reference) => editFlow({ reference })}
                    />

                    {!!missingRows && (
                      <View style={{ marginTop: 14 }}>
                        <Tag
                          text={`${missingRows} row(s) need product or quantity review`}
                          tone="amber"
                        />
                      </View>
                    )}
                  </Panel>

                  {flow.rows.map((row, index) => {
                    const product = products.find((p) => p.id === row.productId);
                    const complete = product && quantityValid(row.quantity);
                    const notes = [
                      ...new Set([
                        ...(Array.isArray(row.reviewNotes) ? row.reviewNotes : []),
                        ...(Array.isArray(row.warnings) ? row.warnings : []),
                      ]),
                    ];

                    return (
                      <Panel key={row.key}>
                        <View style={s.between}>
                          <Text style={s.eyebrow}>MEDICINE {index + 1}</Text>
                          <Tag
                            text={complete ? "Fields complete" : "Needs review"}
                            tone={complete ? "green" : "amber"}
                          />
                        </View>

                        {!!row.sourceText && (
                          <View style={s.sourceBox}>
                            <Text style={s.smallHeading}>SOURCE INSTRUCTION</Text>
                            <Text style={s.body}>{row.sourceText}</Text>
                          </View>
                        )}

                        <Input
                          label="Medicine name"
                          value={row.medicineName}
                          editable={!working}
                          maxLength={200}
                          onChangeText={(value) =>
                            editRow(row.key, "medicineName", value)
                          }
                        />

                        <View style={s.columns}>
                          <Input
                            style={s.flex}
                            label="Recorded strength"
                            value={row.strength}
                            placeholder="Check original"
                            editable={!working}
                            maxLength={80}
                            onChangeText={(value) =>
                              editRow(row.key, "strength", value)
                            }
                          />
                          <Input
                            style={s.flex}
                            label="Pills for this dose"
                            value={row.quantity}
                            placeholder="Needs review"
                            editable={!working}
                            keyboardType="number-pad"
                            maxLength={3}
                            onChangeText={(value) =>
                              editRow(row.key, "quantity", value)
                            }
                          />
                        </View>

                        {!!row.quantityExplanation && (
                          <Text style={[s.caption, { marginTop: 9 }]}>
                            {row.quantityExplanation}
                          </Text>
                        )}

                        <Text style={[s.label, { marginTop: 18 }]}>
                          Exact trained product
                        </Text>
                        <Pressable
                          accessibilityRole="button"
                          disabled={working}
                          style={s.productSelect}
                          onPress={() => {
                            setProductSearch("");
                            setProductRow(row.key);
                          }}
                        >
                          <Text style={s.productSelectText}>
                            {product?.name || "Select supported product"}
                          </Text>
                          <Text style={s.arrow}>⌄</Text>
                        </Pressable>

                        {notes.map((note, noteIndex) => (
                          <Text key={noteIndex} style={s.note}>
                            • {note}
                          </Text>
                        ))}

                        <Pressable
                          disabled={working}
                          style={s.removeButton}
                          onPress={() =>
                            Alert.alert(
                              "Remove medicine?",
                              `Remove ${row.medicineName || "this row"} from the reviewed list?`,
                              [
                                { text: "Cancel", style: "cancel" },
                                {
                                  text: "Remove",
                                  style: "destructive",
                                  onPress: () =>
                                    editFlow({
                                      rows: flow.rows.filter(
                                        (item) => item.key !== row.key
                                      ),
                                    }),
                                },
                              ]
                            )
                          }
                        >
                          <Text style={s.removeText}>Remove row</Text>
                        </Pressable>
                      </Panel>
                    );
                  })}

                  <Panel>
                    <Action
                      title="+ Add medicine"
                      secondary
                      disabled={working || flow.rows.length >= 50}
                      onPress={() =>
                        editFlow({
                          rows: [
                            ...flow.rows,
                            {
                              key: `manual-${Date.now()}`,
                              medicineName: "",
                              strength: "",
                              quantity: "",
                              productId: "",
                            },
                          ],
                        })
                      }
                    />

                    <Pressable
                      accessibilityRole="checkbox"
                      accessibilityState={{ checked: flow.reviewed }}
                      disabled={working}
                      style={s.confirm}
                      onPress={() =>
                        setFlow((current) => ({
                          ...current,
                          reviewed: !current.reviewed,
                          saved: null,
                          result: null,
                        }))
                      }
                    >
                      <View
                        style={[
                          s.checkbox,
                          flow.reviewed && { backgroundColor: C.green },
                        ]}
                      >
                        <Text style={s.checkmark}>
                          {flow.reviewed ? "✓" : ""}
                        </Text>
                      </View>
                      <Text style={[s.body, s.flex]}>
                        I checked every product and quantity against the
                        original instructions for this scheduled dose.
                      </Text>
                    </Pressable>

                    <Action
                      title="Confirm list & continue"
                      disabled={working || !flow.reviewed || !flow.rows.length}
                      onPress={saveReview}
                    />
                    <Action
                      title="Back to prescription"
                      secondary
                      disabled={working}
                      onPress={() =>
                        setFlow((current) => ({ ...current, step: 1 }))
                      }
                    />
                  </Panel>
                </>
              )}

              {flow.step === 3 && (
                <>
                  <Panel>
                    <View style={s.between}>
                      <Text style={s.panelTitle}>Reviewed list saved</Text>
                      <Tag text="Ready to compare" />
                    </View>
                    <Text style={s.caption}>
                      {flow.saved?.items?.length || 0} medicine rows ·{" "}
                      {flow.reference || "One-dose tray"}
                    </Text>
                    <Pressable
                      disabled={working}
                      style={{ marginTop: 12 }}
                      onPress={() =>
                        setFlow((current) => ({ ...current, step: 2 }))
                      }
                    >
                      <Text style={s.link}>Edit reviewed list</Text>
                    </Pressable>
                  </Panel>

                  <PhotoUpload
                    title="Medicine tray photo"
                    photo={flow.trayPhoto}
                    disabled={working}
                    onChoose={() => choosePhoto("tray")}
                    onCamera={() => choosePhoto("tray", true)}
                  />

                  <Panel>
                    <Text style={s.body}>
                      Use even lighting and a plain background. Keep pills
                      separated so their full outlines are visible.
                    </Text>
                    <Action
                      title={flow.result ? "Analyse tray again" : "Analyse & compare"}
                      disabled={
                        working ||
                        !bootstrap ||
                        !flow.trayPhoto ||
                        !flow.saved
                      }
                      onPress={compareTray}
                    />
                  </Panel>

                  {flow.result && <Results result={flow.result} />}

                  <Action
                    title="Start a new review"
                    secondary
                    disabled={working}
                    onPress={resetReview}
                  />
                </>
              )}
            </>
          )}

          {CARE_WORKSPACES[tab] && (
            <>
              <Text style={s.eyebrow}>
                {CARE_WORKSPACES[tab].eyebrow}
              </Text>

              <Text style={s.title}>
                {CARE_WORKSPACES[tab].title}
              </Text>

              <Text style={s.subtitle}>
                {CARE_WORKSPACES[tab].description}
              </Text>

              <Panel>
                <Tag text="Module integration pending" tone="grey" />

                <Text style={[s.panelTitle, { marginTop: 18 }]}>
                  A dedicated care workspace
                </Text>

                <Text style={s.body}>
                  This screen is ready for your team's component.
                  Resident data, predictions and alerts are not connected here yet.
                </Text>
              </Panel>

              {CARE_WORKSPACES[tab].sections.map((section, index) => (
                <Panel key={section.title}>
                  <Text style={s.eyebrow}>
                    WORKSPACE AREA {index + 1}
                  </Text>
                  <Text style={s.panelTitle}>{section.title}</Text>
                  <Text style={s.body}>{section.description}</Text>
                </Panel>
              ))}

              <Action
                title="Back to Home"
                secondary
                disabled={working}
                onPress={() => changeTab("home")}
              />
            </>
          )}

          {tab === "history" && !historyDetail && (
            <>
              <Text style={s.eyebrow}>SAVED COMPARISONS</Text>
              <Text style={s.title}>Your review history.</Text>
              <Text style={s.subtitle}>
                Records from the currently connected medicine API.
              </Text>

              <Input
                label="Search reviews"
                value={historySearch}
                placeholder="Reference, status or date"
                onChangeText={setHistorySearch}
                autoCorrect={false}
              />

              <Action
                title="Refresh history"
                secondary
                disabled={working}
                onPress={loadHistory}
              />

              <View style={{ height: 20 }} />

              {!filteredHistory.length && !working && (
                <Panel>
                  <Text style={s.panelTitle}>
                    {historyLoaded ? "No matching reviews" : "History not loaded"}
                  </Text>
                  <Text style={s.body}>
                    {historyLoaded
                      ? "Completed tray comparisons will appear here."
                      : "Tap Refresh history to load records from your API."}
                  </Text>
                </Panel>
              )}

              {filteredHistory.map((record) => (
                <Pressable
                  key={record.id}
                  disabled={working}
                  onPress={() => setHistoryDetail(record)}
                >
                  <Panel>
                    <Text style={s.panelTitle}>
                      {record.reference || "Medicine tray review"}
                    </Text>
                    <Text style={[s.caption, { marginBottom: 12 }]}>
                      {dateLabel(record.createdAt)}
                    </Text>
                    <Tag
                      text={record.status || "Review required"}
                      tone={comparisonTone(record)}
                    />
                    <Text style={[s.link, { marginTop: 15 }]}>
                      View comparison →
                    </Text>
                  </Panel>
                </Pressable>
              ))}
            </>
          )}

          {tab === "history" && historyDetail && (
            <>
              <Pressable
                disabled={working}
                onPress={() => setHistoryDetail(null)}
                style={{ marginBottom: 20 }}
              >
                <Text style={s.link}>← Back to history</Text>
              </Pressable>
              <Text style={s.title}>
                {historyDetail.reference || "Saved review"}
              </Text>
              <Text style={s.subtitle}>
                {dateLabel(historyDetail.createdAt)}
              </Text>
              <Results result={historyDetail} />
            </>
          )}

          <Text style={s.footer}>
            HyperCare · Research prototype{"\n"}
            Predictions support review; they do not confirm treatment safety.
          </Text>
        </ScrollView>
      </KeyboardAvoidingView>

      <View style={[s.nav, { gap: 4, paddingHorizontal: 8 }]}>
        {[
          ["health", "Health", "heart-outline", "heart"],
          ["activity", "Activity", "walk-outline", "walk"],
          ["nutrition", "Nutrition", "restaurant-outline", "restaurant"],
          ["medicines", "Medicines", "medkit-outline", "medkit"],
          ["settings", "Settings", "settings-outline", "settings"],
        ].map(([key, label, outlineIcon, filledIcon]) => {
          const selected = settingsOpen
            ? key === "settings"
            : key === tab ||
              (key === "medicines" && tab === "history");

          return (
            <Pressable
              key={key}
              accessibilityRole="tab"
              accessibilityLabel={`Open ${label}`}
              accessibilityState={{ selected, disabled: working }}
              disabled={working}
              onPress={() => {
                if (key === "settings") {
                  openSettings();
                } else {
                  changeTab(key);
                }
              }}
              style={({ pressed }) => [
                s.navItem,
                {
                  minHeight: 64,
                  paddingVertical: 8,
                  gap: 5,
                },
                selected && s.navActive,
                (pressed || working) && {
                  opacity: working ? 0.5 : 0.75,
                },
              ]}
            >
              <Ionicons
                name={selected ? filledIcon : outlineIcon}
                size={24}
                color={selected ? C.green : C.muted}
                accessible={false}
              />

              <Text
                numberOfLines={1}
                adjustsFontSizeToFit
                minimumFontScale={0.8}
                style={[
                  s.navText,
                  {
                    fontSize: 10,
                    color: selected ? C.green : C.muted,
                  },
                ]}
              >
                {label}
              </Text>
            </Pressable>
          );
        })}
      </View>

      <Modal
        visible={settingsOpen}
        animationType="slide"
        onRequestClose={() => {
          if (!working) {
            setSettingsOpen(false);
          }
        }}
      >
        <SettingsContent
          apiUrl={apiUrl}
          connection={connection}
          bootstrap={bootstrap}
          working={working}
          onSaveMedicine={(value) => applySettings(value)}
          onClose={() => setSettingsOpen(false)}
        />
      </Modal>

      <Modal
        visible={productRow !== null}
        animationType="slide"
        onRequestClose={() => setProductRow(null)}
      >
        <SafeAreaView style={s.modal}>
          <View style={s.productModalHeader}>
            <Text style={s.eyebrow}>LOCAL TRAINING CATALOG</Text>
            <Text style={s.title}>Choose exact product.</Text>
            <Text style={s.body}>
              Similar spelling does not establish medicine equivalence. Check
              the original product and strength.
            </Text>

            <Input
              label="Search products"
              value={productSearch}
              placeholder="Medicine or strength"
              autoCorrect={false}
              onChangeText={setProductSearch}
            />
          </View>

          <ScrollView
            contentContainerStyle={s.productModalList}
            keyboardShouldPersistTaps="handled"
          >
            {filteredProducts.map((product) => (
              <Pressable
                key={product.id}
                onPress={() => selectProduct(product)}
                style={s.catalogRow}
              >
                <Text style={s.rowTitle}>{product.name}</Text>
                <Text style={s.caption}>
                  {product.strength || "Strength metadata not verified"}
                </Text>
              </Pressable>
            ))}

            {!filteredProducts.length && (
              <Text style={s.body}>No matching trained products.</Text>
            )}
          </ScrollView>

          <View style={{ padding: 20 }}>
            <Action
              title="Close product list"
              secondary
              onPress={() => setProductRow(null)}
            />
          </View>
        </SafeAreaView>
      </Modal>
    </SafeAreaView>
  );
}


const CARE_WORKSPACES = {
  health: {
    eyebrow: "COMPONENT 01 ? HEALTH & BP",
    title: "Health & BP monitoring.",
    description:
      "A dedicated workspace for physiological health information and hypertension assessment.",
    sections: [
      {
        title: "Blood pressure records",
        description:
          "Resident measurements and trends can be connected here.",
      },
      {
        title: "Physiological assessment",
        description:
          "Your team's trained-model assessment can be integrated here.",
      },
      {
        title: "Caregiver review",
        description:
          "Supporting information and assessment records can be reviewed here once connected.",
      },
    ],
  },

  activity: {
    eyebrow: "COMPONENT 02 ? ACTIVITY & SAFETY",
    title: "Activity & safety.",
    description:
      "A dedicated workspace for movement observations and resident-safety support.",
    sections: [
      {
        title: "Activity observations",
        description:
          "The activity component's observations can be displayed here.",
      },
      {
        title: "Safety assessment",
        description:
          "Relevant model results and supporting observations can be connected here.",
      },
      {
        title: "Observation history",
        description:
          "Recorded activity and caregiver reviews can be displayed here.",
      },
    ],
  },

  nutrition: {
    eyebrow: "COMPONENT 03 ? NUTRITION CARE",
    title: "Nutrition care.",
    description:
      "A dedicated workspace for meal information and nutritional-intelligence results.",
    sections: [
      {
        title: "Meal records",
        description:
          "Resident meal entry and review can be integrated here.",
      },
      {
        title: "Nutrient analysis",
        description:
          "The nutrition component's nutrient processing can be connected here.",
      },
      {
        title: "Nutrition insights",
        description:
          "The trained model's assessment and supporting details can be displayed here.",
      },
    ],
  },
};


function makeStyles(C) {
  return StyleSheet.create({
  app: { flex: 1, backgroundColor: C.bg },
  flex: { flex: 1 },
  header: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 22,
    paddingVertical: 15,
    gap: 12,
  },
  logo: { width: 45, height: 45, borderRadius: 14 },
  brand: { color: C.forest, fontSize: 21, fontWeight: "800", letterSpacing: -0.7 },
  brandCaption: { color: C.muted, fontSize: 10, marginTop: 3 },
  settingsButton: {
    paddingHorizontal: 13,
    paddingVertical: 12,
    backgroundColor: C.white,
    borderWidth: 1,
    borderColor: C.border,
    borderRadius: 13,
  },
  settingsText: { color: C.green, fontSize: 11, fontWeight: "700" },
  content: { paddingHorizontal: 20, paddingTop: 20, paddingBottom: 30 },
  eyebrow: { color: C.green, fontSize: 10, fontWeight: "800", letterSpacing: 1.5, marginBottom: 10 },
  title: { color: C.ink, fontSize: 32, lineHeight: 39, fontWeight: "800", letterSpacing: -1.1, marginBottom: 12, marginTop: 3 },
  subtitle: { color: C.muted, fontSize: 14, lineHeight: 22, marginBottom: 24 },
  panel: { backgroundColor: C.white, borderRadius: 21, padding: 20, borderWidth: 1, borderColor: C.border, marginBottom: 16 },
  panelTitle: { color: C.ink, fontSize: 17, fontWeight: "800", lineHeight: 24, marginBottom: 10, flexShrink: 1 },
  body: { color: C.muted, fontSize: 13, lineHeight: 21 },
  caption: { color: C.muted, fontSize: 11, lineHeight: 18 },
  rowTitle: { color: C.ink, fontSize: 14, fontWeight: "700", lineHeight: 21 },
  medicineTitle: { color: C.forest, fontSize: 17, fontWeight: "800", lineHeight: 24, marginBottom: 6 },
  smallHeading: { color: C.muted, fontSize: 9, fontWeight: "800", letterSpacing: 0.8, marginBottom: 7 },
  hero: { backgroundColor: C.forest, padding: 25, borderRadius: 25, marginBottom: 18 },
  heroEyebrow: { color: "#A5D4B9", fontSize: 10, fontWeight: "800", letterSpacing: 1.5 },
  heroTitle: { color: C.white, fontSize: 27, lineHeight: 35, fontWeight: "800", letterSpacing: -0.5, marginTop: 16 },
  heroBody: { color: "#C3D9CB", fontSize: 13, lineHeight: 21, marginTop: 13 },
  heroAction: { backgroundColor: "#E5F3E9", padding: 16, borderRadius: 13, marginTop: 23, minHeight: 50, justifyContent: "center" },
  heroActionText: { color: C.forest, fontSize: 13, fontWeight: "800", textAlign: "center" },
  columns: { flexDirection: "row", gap: 12 },
  between: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 10, flexWrap: "wrap" },
  homeMetric: { fontSize: 30, color: C.forest, fontWeight: "800", marginBottom: 5 },
  sectionHeading: { marginTop: 7, marginBottom: 14 },
  sectionTitle: { color: C.ink, fontSize: 18, fontWeight: "800" },
  quickRow: { flexDirection: "row", alignItems: "center", gap: 13, padding: 17, backgroundColor: C.white, borderWidth: 1, borderColor: C.border, borderRadius: 18, marginBottom: 11 },
  quickIcon: { width: 43, height: 43, backgroundColor: C.mint, borderRadius: 13, alignItems: "center", justifyContent: "center" },
  quickIconText: { color: C.green, fontSize: 23, fontWeight: "700" },
  arrow: { color: C.green, fontSize: 23 },
  tag: { paddingHorizontal: 10, paddingVertical: 7, borderRadius: 9, alignSelf: "flex-start", maxWidth: "100%" },
  tagText: { fontSize: 10, lineHeight: 15, fontWeight: "800" },
  action: { backgroundColor: C.green, borderRadius: 13, paddingHorizontal: 15, paddingVertical: 15, minHeight: 50, alignItems: "center", justifyContent: "center", marginTop: 12 },
  actionSecondary: { backgroundColor: C.mint, borderWidth: 1, borderColor: C.mintBorder },
  actionText: { color: C.white, fontSize: 13, fontWeight: "800", textAlign: "center", lineHeight: 19 },
  inputGroup: { marginTop: 14 },
  label: { color: C.ink, fontSize: 11, fontWeight: "700", marginBottom: 8 },
  input: { borderWidth: 1, borderColor: C.border, backgroundColor: C.bg, borderRadius: 12, padding: 13, minHeight: 48, fontSize: 14, color: C.ink },
  multiline: { minHeight: 150, textAlignVertical: "top", lineHeight: 22 },
  upload: { backgroundColor: C.bg, borderWidth: 1, borderStyle: "dashed", borderColor: "#ADCBB7", borderRadius: 16, minHeight: 210, overflow: "hidden", justifyContent: "center", alignItems: "center", marginTop: 6 },
  uploadSymbol: { width: 54, height: 54, borderRadius: 18, backgroundColor: C.mint, alignItems: "center", justifyContent: "center", marginBottom: 13 },
  uploadPlus: { color: C.green, fontSize: 35 },
  uploadTitle: { color: C.forest, fontSize: 15, fontWeight: "800", marginBottom: 8 },
  uploadHint: { color: C.muted, fontSize: 11, lineHeight: 18, paddingHorizontal: 24, textAlign: "center" },
  uploadPhoto: { width: "100%", height: 250 },
  changePhoto: { backgroundColor: C.mint, width: "100%", padding: 10 },
  changePhotoText: { color: C.green, fontSize: 11, fontWeight: "700", textAlign: "center" },
  steps: { flexDirection: "row", backgroundColor: C.mint, paddingVertical: 15, borderRadius: 18, marginBottom: 22 },
  stepItem: { flex: 1, alignItems: "center", gap: 8 },
  stepNumber: { width: 29, height: 29, borderRadius: 10, backgroundColor: C.white, alignItems: "center", justifyContent: "center" },
  stepActive: { backgroundColor: C.green },
  stepNumberText: { color: C.green, fontWeight: "800", fontSize: 12 },
  stepLabel: { color: C.ink, fontSize: 10, fontWeight: "700" },
  infoBox: { backgroundColor: C.bg, borderRadius: 12, padding: 13, marginTop: 18 },
  sourceBox: { backgroundColor: C.bg, padding: 13, borderRadius: 12, marginTop: 10 },
  productSelect: { flexDirection: "row", alignItems: "center", gap: 10, padding: 13, backgroundColor: C.mint, borderWidth: 1, borderColor: C.mintBorder, borderRadius: 12, minHeight: 49 },
  productSelectText: { flex: 1, color: C.forest, fontSize: 13, fontWeight: "700", lineHeight: 20 },
  note: { color: C.amber, fontSize: 11, lineHeight: 18, marginTop: 9 },
  removeButton: { paddingVertical: 12, marginTop: 8, alignSelf: "flex-start" },
  removeText: { color: C.red, fontSize: 11, fontWeight: "700" },
  confirm: { flexDirection: "row", alignItems: "flex-start", gap: 12, paddingVertical: 18, marginTop: 8 },
  checkbox: { width: 26, height: 26, borderRadius: 7, borderWidth: 1, borderColor: C.green, alignItems: "center", justifyContent: "center", marginTop: 2 },
  checkmark: { color: C.white, fontSize: 17, fontWeight: "800" },
  metrics: { flexDirection: "row", gap: 8, backgroundColor: C.bg, borderRadius: 14, paddingVertical: 17, marginVertical: 18 },
  metric: { flex: 1, alignItems: "center" },
  metricNumber: { color: C.forest, fontSize: 29, fontWeight: "800", marginBottom: 4 },
  countLine: { flexDirection: "row", justifyContent: "space-between", gap: 10, backgroundColor: C.bg, borderRadius: 10, padding: 12, marginVertical: 14 },
  countText: { color: C.ink, fontSize: 12, fontWeight: "700" },
  annotatedPhoto: { width: "100%", height: 340, borderRadius: 14, backgroundColor: C.bg, marginTop: 8, marginBottom: 10 },
  prediction: { flexDirection: "row", alignItems: "center", gap: 10, borderBottomWidth: 1, borderBottomColor: C.border, paddingVertical: 15 },
  disclaimer: { color: C.muted, fontSize: 11, lineHeight: 19, marginHorizontal: 3, marginBottom: 20 },
  link: { color: C.green, fontSize: 12, fontWeight: "800", lineHeight: 20 },
  busyBox: { flexDirection: "row", alignItems: "center", gap: 12, backgroundColor: C.mint, borderRadius: 13, padding: 15, marginBottom: 18 },
  busyText: { flex: 1, color: C.green, fontSize: 12, fontWeight: "600", lineHeight: 19 },
  errorBox: { backgroundColor: C.redBg, borderRadius: 13, padding: 16, marginBottom: 18 },
  errorTitle: { color: C.red, fontSize: 12, fontWeight: "800", marginBottom: 5 },
  errorText: { color: C.red, fontSize: 12, lineHeight: 20 },
  dismiss: { alignSelf: "flex-start", paddingTop: 12, paddingRight: 18 },
  footer: { color: C.muted, fontSize: 10, lineHeight: 18, textAlign: "center", marginTop: 25 },
  nav: { flexDirection: "row", padding: 10, borderTopWidth: 1, borderTopColor: C.border, backgroundColor: C.white, gap: 8 },
  navItem: { flex: 1, minHeight: 49, alignItems: "center", justifyContent: "center", borderRadius: 13, gap: 5 },
  navActive: { backgroundColor: C.mint },
  navDot: { width: 5, height: 5, borderRadius: 3 },
  navText: { fontSize: 11, fontWeight: "800" },
  modal: { flex: 1, backgroundColor: C.bg },
  modalContent: { padding: 22, paddingBottom: 35 },
  productModalHeader: { padding: 22, paddingBottom: 15 },
  productModalList: { paddingHorizontal: 22, paddingBottom: 20 },
  catalogRow: { backgroundColor: C.white, padding: 17, borderWidth: 1, borderColor: C.border, borderRadius: 14, marginBottom: 10 },
});
}
