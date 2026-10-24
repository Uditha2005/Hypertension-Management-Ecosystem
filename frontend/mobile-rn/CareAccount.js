import React, {
  createContext,
  useContext,
  useEffect,
  useState,
} from "react";
import {
  ActivityIndicator,
  Alert,
  Image,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  useColorScheme,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import AsyncStorage from "@react-native-async-storage/async-storage";
import * as SecureStore from "expo-secure-store";

const ThemeContext = createContext(null);
const AccountContext = createContext(null);

const SESSION_KEY = "hypercare-account-session";
const SERVER_KEY = "hypercare-account-server";
const THEME_KEY = "hypercare-theme";

const LIGHT = {
  bg: "#F2F5F2",
  background: "#F2F5F2",
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

const DARK = {
  bg: "#111B16",
  background: "#111B16",
  white: "#1B2921",
  green: "#89D5AC",
  forest: "#C2EBD3",
  mint: "#253E30",
  mintBorder: "#3B5845",
  ink: "#EAF3EC",
  muted: "#ABBCB0",
  border: "#35473A",
  amber: "#E5C47D",
  amberBg: "#3B321F",
  red: "#F3A5A5",
  redBg: "#3D2628",
};

export function useAppTheme() {
  return useContext(ThemeContext);
}

function useAccount() {
  return useContext(AccountContext);
}
export function useAccountServer() {
  const account = useAccount();
  return account?.server || "";
}

async function accountRequest(base, path, method = "GET", body, token) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 20000);

  try {
    const response = await fetch(`${base}/api/auth${path}`, {
      method,
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: controller.signal,
    });

    const raw = await response.text();
    let data;

    try {
      data = JSON.parse(raw);
    } catch {
      throw new Error("The account server returned an unexpected response.");
    }

    if (!response.ok) {
      throw new Error(data.error || `Account request failed: ${response.status}`);
    }

    return data;
  } catch (error) {
    if (error.name === "AbortError") {
      throw new Error("Account server timed out. Check port 5000.");
    }

    if (String(error.message).includes("Network request failed")) {
      throw new Error(
        "Cannot reach the account server. Check the laptop address and port 5000."
      );
    }

    throw error;
  } finally {
    clearTimeout(timer);
  }
}

export function CareProviders({ children }) {
  const system = useColorScheme();
  const [mode, setMode] = useState("system");
  const [loaded, setLoaded] = useState(false);
  const [server, setServer] = useState("http://192.168.8.151:5000");
  const [token, setToken] = useState("");
  const [user, setUser] = useState(null);
  const [restoreError, setRestoreError] = useState("");
  const [restoring, setRestoring] = useState(false);

  const isDark = mode === "dark" || (mode === "system" && system === "dark");
  const colors = isDark ? DARK : LIGHT;

  useEffect(() => {
    let active = true;

    async function initialize() {
      let base = "http://192.168.8.151:5000";

      try {
        const savedMode = await AsyncStorage.getItem(THEME_KEY);
        const savedServer = await AsyncStorage.getItem(SERVER_KEY);

        if (active && ["light", "dark", "system"].includes(savedMode)) {
          setMode(savedMode);
        }

        if (savedServer) base = savedServer;
        if (active) setServer(base);

        const stored = await SecureStore.getItemAsync(SESSION_KEY);

        if (stored) {
          const session = JSON.parse(stored);

          if (session.server === base && session.token) {
            if (active) setToken(session.token);

            try {
              const response = await accountRequest(
                base,
                "/me",
                "GET",
                undefined,
                session.token
              );

              if (active) setUser(response.user);
            } catch (error) {
              if (active) setRestoreError(error.message);
            }
          }
        }
      } catch {
        if (active) {
          setRestoreError("Could not restore the previous session. Sign in again.");
        }
      } finally {
        if (active) setLoaded(true);
      }
    }

    initialize();
    return () => {
      active = false;
    };
  }, []);

  async function changeMode(next) {
    setMode(next);
    await AsyncStorage.setItem(THEME_KEY, next);
  }

  async function persistSession(data) {
    if (!data?.token || !data?.user?.id) {
      throw new Error("The account server returned an invalid session.");
    }

    await SecureStore.setItemAsync(
      SESSION_KEY,
      JSON.stringify({ server, token: data.token })
    );

    setToken(data.token);
    setUser(data.user);
    setRestoreError("");
  }

  async function authenticate(register, values) {
    const data = await accountRequest(
      server,
      register ? "/register" : "/login",
      "POST",
      values
    );

    await persistSession(data);
  }

  async function refreshSession() {
    if (!token) return;
    setRestoring(true);
    setRestoreError("");

    try {
      const data = await accountRequest(
        server,
        "/me",
        "GET",
        undefined,
        token
      );
      setUser(data.user);
    } catch (error) {
      setRestoreError(error.message);
    } finally {
      setRestoring(false);
    }
  }

  async function saveServer(value) {
    const next = value.trim().replace(/\/+$/, "");

    if (!/^https?:\/\/[^/\s?#]+$/i.test(next)) {
      throw new Error("Use an address such as http://192.168.8.151:5000");
    }

    await AsyncStorage.setItem(SERVER_KEY, next);

    if (next !== server) {
      await SecureStore.deleteItemAsync(SESSION_KEY);
      setToken("");
      setUser(null);
    }

    setServer(next);
    setRestoreError("");
  }

  async function saveProfile(values) {
    const data = await accountRequest(
      server,
      "/me",
      "PATCH",
      values,
      token
    );
    setUser(data.user);
  }

  async function changePassword(currentPassword, newPassword) {
    const data = await accountRequest(
      server,
      "/password",
      "POST",
      { currentPassword, newPassword },
      token
    );
    await persistSession(data);
  }

  async function signOut() {
    try {
      await accountRequest(server, "/logout", "POST", {}, token);
    } catch {
      Alert.alert(
        "Device signed out",
        "The server could not be reached to revoke this session. It will expire automatically."
      );
    }

    await SecureStore.deleteItemAsync(SESSION_KEY);
    setToken("");
    setUser(null);
    setRestoreError("");
  }

  return (
    <ThemeContext.Provider
      value={{ colors, mode, isDark, changeMode }}
    >
      <AccountContext.Provider
        value={{
          loaded,
          server,
          token,
          user,
          restoreError,
          restoring,
          authenticate,
          refreshSession,
          saveServer,
          saveProfile,
          changePassword,
          signOut,
        }}
      >
        {children}
      </AccountContext.Provider>
    </ThemeContext.Provider>
  );
}

function FormField({ label, colors, ...props }) {
  return (
    <View style={{ marginTop: 15 }}>
      <Text
        style={{
          color: colors.ink,
          fontWeight: "700",
          fontSize: 12,
          marginBottom: 8,
        }}
      >
        {label}
      </Text>
      <TextInput
        {...props}
        placeholderTextColor={colors.muted}
        style={{
          color: colors.ink,
          backgroundColor: colors.bg,
          borderColor: colors.border,
          borderWidth: 1,
          padding: 14,
          borderRadius: 12,
          minHeight: 49,
          fontSize: 14,
        }}
      />
    </View>
  );
}

function AccountButton({
  title,
  onPress,
  colors,
  secondary = false,
  disabled = false,
}) {
  return (
    <Pressable
      accessibilityRole="button"
      disabled={disabled}
      onPress={onPress}
      style={{
        backgroundColor: secondary ? colors.mint : colors.green,
        padding: 15,
        minHeight: 49,
        borderRadius: 12,
        alignItems: "center",
        justifyContent: "center",
        marginTop: 14,
        opacity: disabled ? 0.45 : 1,
      }}
    >
      <Text
        style={{
          color: secondary ? colors.green : "#102D20",
          fontSize: 13,
          fontWeight: "800",
          textAlign: "center",
        }}
      >
        {title}
      </Text>
    </Pressable>
  );
}

export function AuthGate({ children }) {
  const { colors: C } = useAppTheme();
  const account = useAccount();

  const [register, setRegister] = useState(false);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [showServer, setShowServer] = useState(false);
  const [serverDraft, setServerDraft] = useState(account.server);

  useEffect(() => {
    setServerDraft(account.server);
  }, [account.server]);

  async function submit() {
    if (busy) return;
    setError("");

    if (register && !name.trim()) {
      setError("Enter your full name.");
      return;
    }

    if (register && password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    setBusy(true);

    try {
      await account.authenticate(register, {
        name: name.trim(),
        email: email.trim(),
        password,
      });
      setPassword("");
      setConfirmPassword("");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function updateServer() {
    setBusy(true);
    setError("");

    try {
      await account.saveServer(serverDraft);
      setShowServer(false);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  if (!account.loaded) {
    return (
      <SafeAreaView
        style={{
          flex: 1,
          backgroundColor: C.bg,
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <ActivityIndicator color={C.green} />
        <Text style={{ color: C.muted, marginTop: 15 }}>
          Opening HyperCareâ€¦
        </Text>
      </SafeAreaView>
    );
  }

  if (account.user) return children;

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: C.bg }}>
      <KeyboardAvoidingView
        style={{ flex: 1 }}
        behavior={Platform.OS === "ios" ? "padding" : undefined}
      >
        <ScrollView
          contentContainerStyle={{ padding: 25, paddingBottom: 40 }}
          keyboardShouldPersistTaps="handled"
        >
          <Image
            source={require("./assets/hypercare-icon.png")}
            style={{
              width: 74,
              height: 74,
              borderRadius: 22,
              marginTop: 20,
              marginBottom: 24,
            }}
          />

          <Text
            style={{
              color: C.green,
              fontSize: 11,
              fontWeight: "800",
              letterSpacing: 1.5,
            }}
          >
            HYPERCARE
          </Text>

          <Text
            style={{
              color: C.ink,
              fontSize: 33,
              lineHeight: 41,
              fontWeight: "800",
              marginTop: 10,
            }}
          >
            {register ? "Create your\ncare workspace." : "Welcome back\nto connected care."}
          </Text>

          <Text style={{ color: C.muted, lineHeight: 22, marginTop: 12 }}>
            An elderly-care hypertension management research system.
          </Text>

          <View
            style={{
              backgroundColor: C.white,
              borderRadius: 20,
              padding: 20,
              marginTop: 25,
              borderWidth: 1,
              borderColor: C.border,
            }}
          >
            <Text style={{ color: C.ink, fontSize: 19, fontWeight: "800" }}>
              {register ? "Sign up" : "Sign in"}
            </Text>

            {register && (
              <FormField
                label="Full name"
                colors={C}
                value={name}
                onChangeText={setName}
                maxLength={100}
                editable={!busy}
                autoComplete="name"
              />
            )}

            <FormField
              label="Email"
              colors={C}
              value={email}
              onChangeText={setEmail}
              keyboardType="email-address"
              autoCapitalize="none"
              autoCorrect={false}
              autoComplete="email"
              maxLength={254}
              editable={!busy}
            />

            <FormField
              label={register ? "Password Â· at least 10 characters" : "Password"}
              colors={C}
              value={password}
              onChangeText={setPassword}
              secureTextEntry
              autoCapitalize="none"
              autoCorrect={false}
              maxLength={128}
              editable={!busy}
            />

            {register && (
              <FormField
                label="Confirm password"
                colors={C}
                value={confirmPassword}
                onChangeText={setConfirmPassword}
                secureTextEntry
                autoCapitalize="none"
                autoCorrect={false}
                maxLength={128}
                editable={!busy}
              />
            )}

            {!!(error || account.restoreError) && (
              <Text
                style={{
                  color: C.red,
                  lineHeight: 20,
                  fontSize: 12,
                  marginTop: 15,
                }}
              >
                {error || account.restoreError}
              </Text>
            )}

            <AccountButton
              title={busy ? "Please waitâ€¦" : register ? "Create account" : "Sign in"}
              colors={C}
              disabled={busy || account.restoring}
              onPress={submit}
            />

            <AccountButton
              title={register ? "Already registered? Sign in" : "New here? Create account"}
              colors={C}
              secondary
              disabled={busy}
              onPress={() => {
                setRegister(!register);
                setPassword("");
                setConfirmPassword("");
                setError("");
              }}
            />

            {!!account.token && !register && (
              <AccountButton
                title={account.restoring ? "Checking sessionâ€¦" : "Retry saved session"}
                colors={C}
                secondary
                disabled={busy || account.restoring}
                onPress={account.refreshSession}
              />
            )}
          </View>

          <Pressable
            disabled={busy}
            onPress={() => setShowServer(!showServer)}
            style={{ paddingVertical: 18 }}
          >
            <Text style={{ color: C.green, fontWeight: "700", fontSize: 12 }}>
              Account server settings {showServer ? "âˆ’" : "+"}
            </Text>
          </Pressable>

          {showServer && (
            <View
              style={{
                padding: 17,
                borderRadius: 15,
                backgroundColor: C.white,
              }}
            >
              <FormField
                label="Account API Â· port 5000"
                colors={C}
                value={serverDraft}
                onChangeText={setServerDraft}
                autoCapitalize="none"
                autoCorrect={false}
                keyboardType="url"
                editable={!busy}
              />
              <AccountButton
                title="Save server address"
                colors={C}
                secondary
                disabled={busy}
                onPress={updateServer}
              />
            </View>
          )}

          <Text
            style={{
              color: C.muted,
              fontSize: 11,
              lineHeight: 19,
              marginTop: 15,
            }}
          >
            Account details are stored by the project account service.
            Use research accounts rather than resident-identifying information.
          </Text>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

export function SettingsContent({
  apiUrl,
  connection,
  bootstrap,
  working,
  onSaveMedicine,
  onClose,
}) {
  const { colors: C, mode, changeMode } = useAppTheme();
  const account = useAccount();

  const [section, setSection] = useState("appearance");
  const [name, setName] = useState(account.user?.name || "");
  const [phone, setPhone] = useState(account.user?.phone || "");
  const [careHome, setCareHome] = useState(account.user?.careHome || "");
  const [medicineUrl, setMedicineUrl] = useState(apiUrl);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    setMedicineUrl(apiUrl);
  }, [apiUrl]);

  async function perform(operation, success) {
    if (busy || working) return;

    setBusy(true);
    setError("");
    setMessage("");

    try {
      await operation();
      if (success) setMessage(success);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  function switchSection(next) {
    setSection(section === next ? "" : next);
    setError("");
    setMessage("");
  }

  const disabled = busy || working;

  function sectionButton(key, title, caption) {
    return (
      <Pressable
        disabled={disabled}
        onPress={() => switchSection(key)}
        style={{
          paddingVertical: 18,
          borderBottomWidth: 1,
          borderBottomColor: C.border,
          flexDirection: "row",
          gap: 12,
          alignItems: "center",
        }}
      >
        <View style={{ flex: 1 }}>
          <Text style={{ color: C.ink, fontSize: 15, fontWeight: "800" }}>
            {title}
          </Text>
          <Text style={{ color: C.muted, fontSize: 11, marginTop: 5 }}>
            {caption}
          </Text>
        </View>
        <Text style={{ color: C.green, fontSize: 22 }}>
          {section === key ? "âˆ’" : "+"}
        </Text>
      </Pressable>
    );
  }

  const paragraph = {
    color: C.muted,
    lineHeight: 21,
    fontSize: 12,
    marginTop: 13,
  };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: C.bg }}>
      <KeyboardAvoidingView
        style={{ flex: 1 }}
        behavior={Platform.OS === "ios" ? "padding" : undefined}
      >
        <ScrollView
          contentContainerStyle={{ padding: 22, paddingBottom: 35 }}
          keyboardShouldPersistTaps="handled"
        >
          <Text style={{ color: C.green, fontSize: 10, fontWeight: "800", letterSpacing: 1.5 }}>
            YOUR WORKSPACE
          </Text>
          <Text style={{ color: C.ink, fontSize: 32, fontWeight: "800", marginTop: 9 }}>
            Settings.
          </Text>

          <View
            style={{
              backgroundColor: C.white,
              borderColor: C.border,
              borderWidth: 1,
              borderRadius: 18,
              padding: 19,
              marginTop: 22,
            }}
          >
            <Text style={{ color: C.ink, fontSize: 19, fontWeight: "800" }}>
              {account.user?.name}
            </Text>
            <Text style={{ color: C.muted, fontSize: 12, marginTop: 7 }}>
              {account.user?.email}
            </Text>
          </View>

          {sectionButton("appearance", "Appearance", "Light, dark or follow your phone")}

          {section === "appearance" && (
            <View style={{ marginTop: 15 }}>
              {[
                ["light", "Light"],
                ["dark", "Dark"],
                ["system", "Use device setting"],
              ].map(([value, label]) => (
                <Pressable
                  key={value}
                  disabled={disabled}
                  onPress={() =>
                    perform(() => changeMode(value), "Appearance saved.")
                  }
                  style={{
                    padding: 16,
                    marginBottom: 9,
                    borderRadius: 12,
                    backgroundColor: mode === value ? C.mint : C.white,
                    borderWidth: 1,
                    borderColor: mode === value ? C.green : C.border,
                    flexDirection: "row",
                    justifyContent: "space-between",
                  }}
                >
                  <Text style={{ color: C.ink, fontWeight: "700" }}>{label}</Text>
                  <Text style={{ color: C.green }}>{mode === value ? "âœ“" : ""}</Text>
                </Pressable>
              ))}
            </View>
          )}

          {sectionButton("profile", "My profile", "Edit your account details")}

          {section === "profile" && (
            <View>
              <FormField label="Full name" colors={C} value={name} onChangeText={setName} maxLength={100} editable={!disabled} />
              <FormField label="Phone Â· optional" colors={C} value={phone} onChangeText={setPhone} maxLength={30} keyboardType="phone-pad" editable={!disabled} />
              <FormField label="Care-home name Â· optional" colors={C} value={careHome} onChangeText={setCareHome} maxLength={150} editable={!disabled} />
              <Text style={paragraph}>Account email: {account.user?.email}</Text>
              <AccountButton
                title="Save profile"
                colors={C}
                disabled={disabled}
                onPress={() =>
                  perform(
                    () => account.saveProfile({ name, phone, careHome }),
                    "Profile saved."
                  )
                }
              />
            </View>
          )}

          {sectionButton("password", "Password", "Change your account password")}

          {section === "password" && (
            <View>
              <FormField label="Current password" colors={C} value={currentPassword} onChangeText={setCurrentPassword} secureTextEntry maxLength={128} editable={!disabled} />
              <FormField label="New password Â· at least 10 characters" colors={C} value={newPassword} onChangeText={setNewPassword} secureTextEntry maxLength={128} editable={!disabled} />
              <FormField label="Confirm new password" colors={C} value={confirmation} onChangeText={setConfirmation} secureTextEntry maxLength={128} editable={!disabled} />
              <AccountButton
                title="Update password"
                colors={C}
                disabled={disabled}
                onPress={() =>
                  perform(async () => {
                    if (newPassword !== confirmation) {
                      throw new Error("New passwords do not match.");
                    }
                    await account.changePassword(currentPassword, newPassword);
                    setCurrentPassword("");
                    setNewPassword("");
                    setConfirmation("");
                  }, "Password updated. Previous sessions were revoked.")
                }
              />
            </View>
          )}

          {sectionButton("privacy", "Privacy & data", "Understand how this prototype handles information")}

          {section === "privacy" && (
            <View>
              <Text style={paragraph}>
                PROFILE{"\n"}
                Your account name, email and optional profile details are stored
                in the SQLite account database on the project backend. Passwords are stored as salted
                hashes, not plain text.
              </Text>
              <Text style={paragraph}>
                DEVICE STORAGE{"\n"}
                Session tokens use SecureStore. Theme and server preferences
                use local app storage. Your password is not saved on this device.
              </Text>
              <Text style={paragraph}>
                MEDICINE PROCESSING{"\n"}
                Prescription and tray photos go to the laptop medicine API.
                With LLM extraction enabled, prescription text is sent to Groq.
                Use de-identified research samples.
              </Text>
              <Text style={paragraph}>
                SHARED MEDICINE HISTORY{"\n"}
                The existing medicine API stores comparisons in its local
                database. These records are shared at that API and are not yet
                separated by signed-in account.
              </Text>
              <Text style={paragraph}>
                LOCAL DEVELOPMENT{"\n"}
                An http:// server address is an unencrypted local development
                connection. This prototype is not configured for handling
                identifiable resident data over a production network.
              </Text>
            </View>
          )}

          {sectionButton("connection", "Connection", "Medicine API and account service")}

          {section === "connection" && (
            <View>
              <Text style={paragraph}>Medicine service: {connection}</Text>
              <FormField
                label="Medicine API address Â· port 8000"
                colors={C}
                value={medicineUrl}
                onChangeText={setMedicineUrl}
                autoCapitalize="none"
                autoCorrect={false}
                keyboardType="url"
                editable={!disabled}
              />
              <AccountButton
                title="Save & test medicine connection"
                colors={C}
                secondary
                disabled={disabled}
                onPress={() => onSaveMedicine(medicineUrl)}
              />
              <Text style={paragraph}>
                Account service: {account.server}
                {"\n"}
                Model: {bootstrap?.modelFile || "Not connected"}
                {"\n"}
                OCR: {bootstrap?.ocrConfigured ? "Configured" : "Not configured"}
                {"\n"}
                Groq: {bootstrap?.llmConfigured ? "Configured" : "Not configured"}
              </Text>
              <Text style={paragraph}>
                To change the account server, sign out and open Account server
                settings on the sign-in screen.
              </Text>
            </View>
          )}

          {sectionButton("about", "About HyperCare", "Version and research information")}

          {section === "about" && (
            <Text style={paragraph}>
              HyperCare Â· Version 1.0.0
              {"\n\n"}
              Elderly-care hypertension management research prototype.
              {"\n\n"}
              Care workspaces: health and BP, activity and safety, nutrition,
              and medicine verification.
              {"\n\n"}
              AI outputs require appropriate human review and do not confirm
              treatment safety.
            </Text>
          )}

          {(busy || working) && (
            <View style={{ flexDirection: "row", gap: 10, marginTop: 18 }}>
              <ActivityIndicator color={C.green} />
              <Text style={{ color: C.muted }}>Please waitâ€¦</Text>
            </View>
          )}

          {!!error && <Text style={{ color: C.red, marginTop: 17, lineHeight: 21 }}>{error}</Text>}
          {!!message && <Text style={{ color: C.green, marginTop: 17, lineHeight: 21 }}>{message}</Text>}

          <AccountButton
            title="Sign out"
            colors={C}
            secondary
            disabled={disabled}
            onPress={() =>
              Alert.alert(
                "Sign out?",
                "Any unfinished medicine review will be cleared from this app session.",
                [
                  { text: "Cancel", style: "cancel" },
                  {
                    text: "Sign out",
                    style: "destructive",
                    onPress: () => perform(account.signOut),
                  },
                ]
              )
            }
          />

          <AccountButton
            title="Close settings"
            colors={C}
            secondary
            disabled={disabled}
            onPress={onClose}
          />
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}