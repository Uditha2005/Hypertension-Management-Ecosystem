import React, { useState } from "react";
import {
  ActivityIndicator,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";
import {
  getSdkStatus,
  initialize,
  requestPermission,
  getGrantedPermissions,
  readRecords,
  openHealthConnectSettings,
  SdkAvailabilityStatus,
} from "react-native-health-connect";

const BLOOD_PRESSURE_PERMISSION = {
  accessType: "read",
  recordType: "BloodPressure",
};
const HEART_RATE_PERMISSION = {
  accessType: "read",
  recordType: "HeartRate",
};
const DAYS_TO_READ = 30;
const MAX_RECORDS = 50;

function makeStyles(colors) {
  return StyleSheet.create({
    card: {
      backgroundColor: colors.white,
      borderColor: colors.border,
      borderWidth: 1,
      borderRadius: 16,
      padding: 15,
      gap: 12,
    },
    title: {
      color: colors.ink,
      fontSize: 18,
      fontWeight: "800",
    },
    subtitle: {
      color: colors.muted,
      fontSize: 12,
      lineHeight: 18,
    },
    note: {
      backgroundColor: colors.amberBg,
      borderColor: colors.amber,
      borderWidth: 1,
      borderRadius: 10,
      padding: 11,
      gap: 4,
    },
    noteText: {
      color: colors.ink,
      fontSize: 11,
      lineHeight: 17,
    },
    button: {
      minHeight: 45,
      paddingHorizontal: 12,
      paddingVertical: 10,
      alignItems: "center",
      justifyContent: "center",
      borderRadius: 10,
      backgroundColor: colors.green,
      flexDirection: "row",
      gap: 8,
    },
    buttonDisabled: {
      opacity: 0.6,
    },
    buttonText: {
      color: "#FFFFFF",
      fontSize: 13,
      fontWeight: "800",
      textAlign: "center",
    },
    secondaryButton: {
      borderWidth: 1,
      borderColor: colors.border,
      borderRadius: 9,
      minHeight: 38,
      alignItems: "center",
      justifyContent: "center",
      paddingHorizontal: 11,
      paddingVertical: 8,
    },
    secondaryText: {
      color: colors.green,
      fontSize: 12,
      fontWeight: "800",
    },
    message: {
      color: colors.muted,
      fontSize: 12,
      lineHeight: 18,
    },
    error: {
      backgroundColor: colors.redBg,
      borderColor: colors.red,
      borderWidth: 1,
      borderRadius: 10,
      padding: 11,
      gap: 8,
    },
    errorText: {
      color: colors.red,
      fontSize: 12,
      lineHeight: 18,
    },
    record: {
      borderTopWidth: 1,
      borderTopColor: colors.border,
      paddingTop: 12,
      gap: 9,
    },
    recordTime: {
      color: colors.muted,
      fontSize: 11,
    },
    readings: {
      flexDirection: "row",
      gap: 10,
    },
    readingValue: {
      flex: 1,
      backgroundColor: colors.bg,
      borderRadius: 9,
      padding: 10,
      gap: 3,
    },
    readingLabel: {
      color: colors.muted,
      fontSize: 10,
      fontWeight: "700",
    },
    readingNumber: {
      color: colors.ink,
      fontSize: 19,
      fontWeight: "800",
    },
    unit: {
      color: colors.muted,
      fontSize: 10,
    },
  });
}

function formatTimestamp(value) {
  const date = new Date(value);

  if (!value || Number.isNaN(date.getTime())) {
    return "Recording time unavailable";
  }

  return date.toLocaleString();
}

export default function HealthConnectSection({
  colors,
  disabled = false,
  onSelectReading,
  onRecordsLoaded,
  onHeartRateLoaded,
}) {
  const styles = React.useMemo(() => makeStyles(colors), [colors]);

  const [loading, setLoading] = useState(false);
  const [records, setRecords] = useState([]);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [latestHeartRate, setLatestHeartRate] = useState(null);
  const [heartRateMessage, setHeartRateMessage] = useState("");

  async function connectAndLoad() {
    if (Platform.OS !== "android") {
      setError("Health Connect is supported by this Android app only.");
      return;
    }

    setLoading(true);
    setError("");
    setMessage("");

    try {
      const sdkStatus = await getSdkStatus();

      if (sdkStatus !== SdkAvailabilityStatus.SDK_AVAILABLE) {
        setError(
          sdkStatus ===
            SdkAvailabilityStatus.SDK_UNAVAILABLE_PROVIDER_UPDATE_REQUIRED
            ? "Health Connect needs to be installed or updated on this phone."
            : "Health Connect is not available on this phone."
        );
        return;
      }

      const initialized = await initialize();

      if (!initialized) {
        setError("Could not initialize Health Connect. Please try again.");
        return;
      }

      await requestPermission([
       BLOOD_PRESSURE_PERMISSION,
       HEART_RATE_PERMISSION,
      ]);

      const grantedPermissions = await getGrantedPermissions();

      const hasBloodPressureAccess = grantedPermissions.some(
        (permission) =>
          permission.accessType === "read" &&
          permission.recordType === "BloodPressure"
      );
      const hasHeartRateAccess = grantedPermissions.some(
        (permission) =>
          permission.accessType === "read" &&
          permission.recordType === "HeartRate"
      );

      if (!hasBloodPressureAccess) {
        setError(
          "Blood-pressure read permission was not granted. You can try again or open Health Connect settings."
        );
        return;
      }

      const endDate = new Date();
      const startDate = new Date(
        endDate.getTime() - DAYS_TO_READ * 24 * 60 * 60 * 1000
      );

      const response = await readRecords("BloodPressure", {
        timeRangeFilter: {
          operator: "between",
          startTime: startDate.toISOString(),
          endTime: endDate.toISOString(),
        },
        pageSize: MAX_RECORDS,
        ascendingOrder: false,
      });

      const safeRecords = (response.records || [])
        .map((record) => ({
          id: record.metadata?.id || `${record.time}-${Math.random()}`,
          time: record.time,
          systolic: Number(
            record.systolic?.inMillimetersOfMercury
          ),
          diastolic: Number(
            record.diastolic?.inMillimetersOfMercury
          ),
        }))
        .filter(
          (record) =>
            record.time &&
            Number.isFinite(new Date(record.time).getTime()) &&
            Number.isFinite(record.systolic) &&
            Number.isFinite(record.diastolic) &&
            record.systolic > 0 &&
            record.diastolic > 0
        )
        .sort(
          (first, second) =>
            new Date(second.time).getTime() -
            new Date(first.time).getTime()
        );

      let newestHeartRate = null;
      let heartRateStatus = "";

      if (hasHeartRateAccess) {
        try {
          const heartRateResponse = await readRecords("HeartRate", {
            timeRangeFilter: {
              operator: "between",
              startTime: startDate.toISOString(),
              endTime: endDate.toISOString(),
            },
            pageSize: MAX_RECORDS,
            ascendingOrder: false,
          });

          const validSamples = (heartRateResponse.records || [])
            .flatMap((record) =>
              Array.isArray(record.samples) ? record.samples : []
            )
            .map((sample) => ({
              time: sample.time,
              bpm: Number(sample.beatsPerMinute),
            }))
            .filter(
              (sample) =>
                sample.time &&
                Number.isFinite(new Date(sample.time).getTime()) &&
                Number.isFinite(sample.bpm) &&
                sample.bpm > 0
            )
            .sort(
              (first, second) =>
                new Date(second.time).getTime() -
                new Date(first.time).getTime()
            );

          newestHeartRate = validSamples[0] || null;

          heartRateStatus = newestHeartRate
            ? `Latest heart-rate sample: ${newestHeartRate.bpm} BPM, recorded ${formatTimestamp(newestHeartRate.time)}.`
            : `No heart-rate samples were found in the last ${DAYS_TO_READ} days.`;
        } catch (heartRateError) {
          heartRateStatus =
            heartRateError?.message ||
            "Could not read heart-rate data. Check Health Connect permissions.";
        }
      } else {
        heartRateStatus =
          "Heart-rate read permission is not granted. Check Health Connect settings.";
      }

      setLatestHeartRate(newestHeartRate);
      setHeartRateMessage(heartRateStatus);
      onHeartRateLoaded?.(newestHeartRate);

      setRecords(safeRecords);
      onRecordsLoaded?.(safeRecords);
      setMessage(
        safeRecords.length > 0
          ? `Loaded ${safeRecords.length} blood-pressure reading(s) from the last ${DAYS_TO_READ} days.`
          : `Connected successfully, but no blood-pressure readings were found in the last ${DAYS_TO_READ} days.`
      );
    } catch (err) {
      setError(
        err?.message ||
          "Health Connect could not be read. Check its installation, permissions, and try again."
      );
    } finally {
      setLoading(false);
    }
  }

  function openSettings() {
    try {
      openHealthConnectSettings();
    } catch (err) {
      setError(
        err?.message ||
          "Could not open Health Connect settings on this phone."
      );
    }
  }

  function selectReading(record) {
    onSelectReading?.({
      systolic: record.systolic,
      diastolic: record.diastolic,
      time: record.time,
    });
  }

  return (
    <View style={styles.card}>
      <Text style={styles.title}>Health Connect readings</Text>

      <Text style={styles.subtitle}>
        Read-only access to blood-pressure records stored on this phone.
        The screen checks the most recent 30 days and displays up to 50
        readings.
      </Text>

      <View style={styles.note}>
        <Text style={styles.noteText}>
          Only import a reading after confirming that it belongs to the
          intended resident. Verify its timestamp and values before using
          it for an assessment. Selecting a reading only fills the form;
          it does not submit a prediction.
        </Text>
      </View>

      <Pressable
        accessibilityRole="button"
        disabled={loading || disabled}
        onPress={connectAndLoad}
        style={[
          styles.button,
          (loading || disabled) && styles.buttonDisabled,
        ]}
      >
        {loading && <ActivityIndicator color="#FFFFFF" />}
        <Text style={styles.buttonText}>
          {loading
            ? "Connecting and reading…"
            : records.length
              ? "Refresh blood-pressure readings"
              : "Connect Health Connect"}
        </Text>
      </Pressable>

      {!!message && <Text style={styles.message}>{message}</Text>}
      {!!heartRateMessage && (
  <Text style={styles.message}>{heartRateMessage}</Text>
)}

{latestHeartRate && (
  <View style={styles.record}>
    <Text style={styles.recordTime}>
      Heart rate recorded: {formatTimestamp(latestHeartRate.time)}
    </Text>

    <View style={styles.readings}>
      <View style={styles.readingValue}>
        <Text style={styles.readingLabel}>HEART RATE</Text>
        <Text style={styles.readingNumber}>
          {latestHeartRate.bpm}
        </Text>
        <Text style={styles.unit}>BPM</Text>
      </View>
    </View>
  </View>
)}

      {!!error && (
        <View style={styles.error}>
          <Text style={styles.errorText}>{error}</Text>

          <Pressable
            accessibilityRole="button"
            onPress={openSettings}
            style={styles.secondaryButton}
          >
            <Text style={styles.secondaryText}>
              Open Health Connect settings
            </Text>
          </Pressable>
        </View>
      )}

      {records.map((record) => (
        <View key={record.id} style={styles.record}>
          <Text style={styles.recordTime}>
            Recorded: {formatTimestamp(record.time)}
          </Text>

          <View style={styles.readings}>
            <View style={styles.readingValue}>
              <Text style={styles.readingLabel}>SYSTOLIC</Text>
              <Text style={styles.readingNumber}>
                {record.systolic}
              </Text>
              <Text style={styles.unit}>mmHg</Text>
            </View>

            <View style={styles.readingValue}>
              <Text style={styles.readingLabel}>DIASTOLIC</Text>
              <Text style={styles.readingNumber}>
                {record.diastolic}
              </Text>
              <Text style={styles.unit}>mmHg</Text>
            </View>
          </View>

          <Pressable
            accessibilityRole="button"
            disabled={disabled || loading}
            onPress={() => selectReading(record)}
            style={[
              styles.secondaryButton,
              (disabled || loading) && styles.buttonDisabled,
            ]}
          >
            <Text style={styles.secondaryText}>
              Use these BP values
            </Text>
          </Pressable>
        </View>
      ))}
    </View>
  );
}