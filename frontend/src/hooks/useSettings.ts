import { useState, useEffect, useCallback } from "react";
import {
  getSettings,
  saveSettings,
  type SettingsResponse,
  type SettingsUpdate,
} from "../api/settings";

interface UseSettingsReturn {
  settings: SettingsResponse | null;
  loading: boolean;
  error: string | null;
  saving: boolean;
  saveError: string | null;
  save: (data: SettingsUpdate) => Promise<void>;
  reload: () => Promise<void>;
}

export function useSettings(userId: number): UseSettingsReturn {
  const [settings, setSettings] = useState<SettingsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const fetchSettings = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const result = await getSettings(userId);
      setSettings(result);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Failed to load settings";
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [userId]);

  const save = useCallback(
    async (data: SettingsUpdate) => {
      setSaving(true);
      setSaveError(null);

      try {
        const updated = await saveSettings(userId, data);
        setSettings(updated);
      } catch (err) {
        const message =
          err instanceof Error ? err.message : "Failed to save settings";
        setSaveError(message);
        throw err;
      } finally {
        setSaving(false);
      }
    },
    [userId]
  );

  useEffect(() => {
    fetchSettings();
  }, [fetchSettings]);

  return {
    settings,
    loading,
    error,
    saving,
    saveError,
    save,
    reload: fetchSettings,
  };
}

export default useSettings;
