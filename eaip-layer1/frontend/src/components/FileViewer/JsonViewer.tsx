import { type FC, useState, useEffect, useCallback } from "react";

interface JsonViewerProps {
  fileId: number;
}

// --- Recursive JSON tree node component ---

type JsonValue =
  | string
  | number
  | boolean
  | null
  | JsonValue[]
  | { [key: string]: JsonValue };

interface JsonNodeProps {
  keyName?: string;
  value: JsonValue;
  depth: number;
  isLast: boolean;
}

const JsonNode: FC<JsonNodeProps> = ({ keyName, value, depth, isLast }) => {
  const [collapsed, setCollapsed] = useState(depth > 1);
  const indent = depth * 16;

  const toggle = useCallback(() => setCollapsed((c) => !c), []);

  // Render primitive values
  if (value === null) {
    return (
      <div className="flex" style={{ paddingLeft: `${indent}px` }}>
        {keyName !== undefined && (
          <>
            <span className="text-purple-300">&quot;{keyName}&quot;</span>
            <span className="text-gray-400">:&nbsp;</span>
          </>
        )}
        <span className="text-orange-400">null</span>
        {!isLast && <span className="text-gray-400">,</span>}
      </div>
    );
  }

  if (typeof value === "boolean") {
    return (
      <div className="flex" style={{ paddingLeft: `${indent}px` }}>
        {keyName !== undefined && (
          <>
            <span className="text-purple-300">&quot;{keyName}&quot;</span>
            <span className="text-gray-400">:&nbsp;</span>
          </>
        )}
        <span className="text-orange-400">{value.toString()}</span>
        {!isLast && <span className="text-gray-400">,</span>}
      </div>
    );
  }

  if (typeof value === "number") {
    return (
      <div className="flex" style={{ paddingLeft: `${indent}px` }}>
        {keyName !== undefined && (
          <>
            <span className="text-purple-300">&quot;{keyName}&quot;</span>
            <span className="text-gray-400">:&nbsp;</span>
          </>
        )}
        <span className="text-cyan-300">{value}</span>
        {!isLast && <span className="text-gray-400">,</span>}
      </div>
    );
  }

  if (typeof value === "string") {
    return (
      <div className="flex" style={{ paddingLeft: `${indent}px` }}>
        {keyName !== undefined && (
          <>
            <span className="text-purple-300">&quot;{keyName}&quot;</span>
            <span className="text-gray-400">:&nbsp;</span>
          </>
        )}
        <span className="text-green-300">&quot;{value}&quot;</span>
        {!isLast && <span className="text-gray-400">,</span>}
      </div>
    );
  }

  // Render arrays
  if (Array.isArray(value)) {
    const items = value;
    const isEmpty = items.length === 0;

    if (isEmpty) {
      return (
        <div className="flex" style={{ paddingLeft: `${indent}px` }}>
          {keyName !== undefined && (
            <>
              <span className="text-purple-300">&quot;{keyName}&quot;</span>
              <span className="text-gray-400">:&nbsp;</span>
            </>
          )}
          <span className="text-gray-300">[]</span>
          {!isLast && <span className="text-gray-400">,</span>}
        </div>
      );
    }

    return (
      <div>
        <div
          className="flex cursor-pointer hover:bg-surface-200 select-none"
          style={{ paddingLeft: `${indent}px` }}
          onClick={toggle}
          role="button"
          aria-expanded={!collapsed}
          aria-label={`Toggle array${keyName ? ` ${keyName}` : ""}`}
        >
          <span className="text-gray-500 w-4 inline-block text-center mr-1">
            {collapsed ? "▶" : "▼"}
          </span>
          {keyName !== undefined && (
            <>
              <span className="text-purple-300">&quot;{keyName}&quot;</span>
              <span className="text-gray-400">:&nbsp;</span>
            </>
          )}
          <span className="text-gray-300">[</span>
          {collapsed && (
            <>
              <span className="text-gray-500 ml-1">
                {items.length} {items.length === 1 ? "item" : "items"}
              </span>
              <span className="text-gray-300">]</span>
              {!isLast && <span className="text-gray-400">,</span>}
            </>
          )}
        </div>
        {!collapsed && (
          <>
            {items.map((item, index) => (
              <JsonNode
                key={index}
                value={item}
                depth={depth + 1}
                isLast={index === items.length - 1}
              />
            ))}
            <div className="flex" style={{ paddingLeft: `${indent}px` }}>
              <span className="w-4 inline-block mr-1" />
              <span className="text-gray-300">]</span>
              {!isLast && <span className="text-gray-400">,</span>}
            </div>
          </>
        )}
      </div>
    );
  }

  // Render objects
  if (typeof value === "object") {
    const entries = Object.entries(value);
    const isEmpty = entries.length === 0;

    if (isEmpty) {
      return (
        <div className="flex" style={{ paddingLeft: `${indent}px` }}>
          {keyName !== undefined && (
            <>
              <span className="text-purple-300">&quot;{keyName}&quot;</span>
              <span className="text-gray-400">:&nbsp;</span>
            </>
          )}
          <span className="text-gray-300">{"{}"}</span>
          {!isLast && <span className="text-gray-400">,</span>}
        </div>
      );
    }

    return (
      <div>
        <div
          className="flex cursor-pointer hover:bg-surface-200 select-none"
          style={{ paddingLeft: `${indent}px` }}
          onClick={toggle}
          role="button"
          aria-expanded={!collapsed}
          aria-label={`Toggle object${keyName ? ` ${keyName}` : ""}`}
        >
          <span className="text-gray-500 w-4 inline-block text-center mr-1">
            {collapsed ? "▶" : "▼"}
          </span>
          {keyName !== undefined && (
            <>
              <span className="text-purple-300">&quot;{keyName}&quot;</span>
              <span className="text-gray-400">:&nbsp;</span>
            </>
          )}
          <span className="text-gray-300">{"{"}</span>
          {collapsed && (
            <>
              <span className="text-gray-500 ml-1">
                {entries.length} {entries.length === 1 ? "key" : "keys"}
              </span>
              <span className="text-gray-300">{"}"}</span>
              {!isLast && <span className="text-gray-400">,</span>}
            </>
          )}
        </div>
        {!collapsed && (
          <>
            {entries.map(([key, val], index) => (
              <JsonNode
                key={key}
                keyName={key}
                value={val}
                depth={depth + 1}
                isLast={index === entries.length - 1}
              />
            ))}
            <div className="flex" style={{ paddingLeft: `${indent}px` }}>
              <span className="w-4 inline-block mr-1" />
              <span className="text-gray-300">{"}"}</span>
              {!isLast && <span className="text-gray-400">,</span>}
            </div>
          </>
        )}
      </div>
    );
  }

  return null;
};

// --- Main JsonViewer component ---

const JsonViewer: FC<JsonViewerProps> = ({ fileId }) => {
  const [data, setData] = useState<JsonValue | undefined>(undefined);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function fetchJson() {
      setLoading(true);
      setError(null);
      setData(undefined);

      try {
        const response = await fetch(`/api/files/${fileId}/content`);
        if (!response.ok) {
          throw new Error(
            `Failed to fetch file content (${response.status} ${response.statusText})`
          );
        }
        const text = await response.text();
        const parsed = JSON.parse(text);
        if (!cancelled) {
          setData(parsed);
        }
      } catch (err) {
        if (!cancelled) {
          if (err instanceof SyntaxError) {
            setError("Invalid JSON: unable to parse file content");
          } else if (err instanceof Error) {
            setError(err.message);
          } else {
            setError("An unexpected error occurred");
          }
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    fetchJson();
    return () => {
      cancelled = true;
    };
  }, [fileId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full text-gray-400">
        <div className="flex items-center gap-2">
          <svg
            className="animate-spin h-5 w-5 text-primary"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
          >
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
            />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
            />
          </svg>
          Loading JSON...
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-full text-danger">
        <div className="text-center">
          <p className="text-lg font-medium">Error</p>
          <p className="text-sm text-gray-400 mt-1">{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full overflow-auto p-4 font-mono text-sm leading-6 bg-surface">
      <JsonNode value={data as JsonValue} depth={0} isLast={true} />
    </div>
  );
};

export default JsonViewer;
