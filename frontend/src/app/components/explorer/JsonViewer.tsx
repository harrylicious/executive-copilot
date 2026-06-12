import { type FC, useState, useEffect, useCallback } from "react";
import { getFileContentUrl } from "../../../api/kb";

interface JsonViewerProps {
  fileId: number;
}

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

  if (value === null) {
    return (
      <div className="flex" style={{ paddingLeft: `${indent}px` }}>
        {keyName !== undefined && (
          <><span className="text-purple-400">&quot;{keyName}&quot;</span><span className="text-muted-foreground">:&nbsp;</span></>
        )}
        <span className="text-orange-400">null</span>
        {!isLast && <span className="text-muted-foreground">,</span>}
      </div>
    );
  }

  if (typeof value === "boolean") {
    return (
      <div className="flex" style={{ paddingLeft: `${indent}px` }}>
        {keyName !== undefined && (
          <><span className="text-purple-400">&quot;{keyName}&quot;</span><span className="text-muted-foreground">:&nbsp;</span></>
        )}
        <span className="text-orange-400">{value.toString()}</span>
        {!isLast && <span className="text-muted-foreground">,</span>}
      </div>
    );
  }

  if (typeof value === "number") {
    return (
      <div className="flex" style={{ paddingLeft: `${indent}px` }}>
        {keyName !== undefined && (
          <><span className="text-purple-400">&quot;{keyName}&quot;</span><span className="text-muted-foreground">:&nbsp;</span></>
        )}
        <span className="text-cyan-400">{value}</span>
        {!isLast && <span className="text-muted-foreground">,</span>}
      </div>
    );
  }

  if (typeof value === "string") {
    return (
      <div className="flex" style={{ paddingLeft: `${indent}px` }}>
        {keyName !== undefined && (
          <><span className="text-purple-400">&quot;{keyName}&quot;</span><span className="text-muted-foreground">:&nbsp;</span></>
        )}
        <span className="text-green-400">&quot;{value}&quot;</span>
        {!isLast && <span className="text-muted-foreground">,</span>}
      </div>
    );
  }

  if (Array.isArray(value)) {
    const items = value;
    const isEmpty = items.length === 0;

    if (isEmpty) {
      return (
        <div className="flex" style={{ paddingLeft: `${indent}px` }}>
          {keyName !== undefined && (
            <><span className="text-purple-400">&quot;{keyName}&quot;</span><span className="text-muted-foreground">:&nbsp;</span></>
          )}
          <span className="text-muted-foreground">[]</span>
          {!isLast && <span className="text-muted-foreground">,</span>}
        </div>
      );
    }

    return (
      <div>
        <div className="flex cursor-pointer hover:bg-muted/50 select-none" style={{ paddingLeft: `${indent}px` }} onClick={toggle}>
          <span className="text-muted-foreground w-4 inline-block text-center mr-1">{collapsed ? "▶" : "▼"}</span>
          {keyName !== undefined && (
            <><span className="text-purple-400">&quot;{keyName}&quot;</span><span className="text-muted-foreground">:&nbsp;</span></>
          )}
          <span className="text-muted-foreground">[</span>
          {collapsed && (
            <><span className="text-muted-foreground ml-1">{items.length} {items.length === 1 ? "item" : "items"}</span><span className="text-muted-foreground">]</span>{!isLast && <span className="text-muted-foreground">,</span>}</>
          )}
        </div>
        {!collapsed && (
          <>
            {items.map((item, index) => (
              <JsonNode key={index} value={item} depth={depth + 1} isLast={index === items.length - 1} />
            ))}
            <div className="flex" style={{ paddingLeft: `${indent}px` }}>
              <span className="w-4 inline-block mr-1" />
              <span className="text-muted-foreground">]</span>
              {!isLast && <span className="text-muted-foreground">,</span>}
            </div>
          </>
        )}
      </div>
    );
  }

  if (typeof value === "object") {
    const entries = Object.entries(value);
    const isEmpty = entries.length === 0;

    if (isEmpty) {
      return (
        <div className="flex" style={{ paddingLeft: `${indent}px` }}>
          {keyName !== undefined && (
            <><span className="text-purple-400">&quot;{keyName}&quot;</span><span className="text-muted-foreground">:&nbsp;</span></>
          )}
          <span className="text-muted-foreground">{}</span>
          {!isLast && <span className="text-muted-foreground">,</span>}
        </div>
      );
    }

    return (
      <div>
        <div className="flex cursor-pointer hover:bg-muted/50 select-none" style={{ paddingLeft: `${indent}px` }} onClick={toggle}>
          <span className="text-muted-foreground w-4 inline-block text-center mr-1">{collapsed ? "▶" : "▼"}</span>
          {keyName !== undefined && (
            <><span className="text-purple-400">&quot;{keyName}&quot;</span><span className="text-muted-foreground">:&nbsp;</span></>
          )}
          <span className="text-muted-foreground">{}</span>
          {collapsed && (
            <><span className="text-muted-foreground ml-1">{entries.length} {entries.length === 1 ? "key" : "keys"}</span><span className="text-muted-foreground">{}</span>{!isLast && <span className="text-muted-foreground">,</span>}</>
          )}
        </div>
        {!collapsed && (
          <>
            {entries.map(([key, val], index) => (
              <JsonNode key={key} keyName={key} value={val} depth={depth + 1} isLast={index === entries.length - 1} />
            ))}
            <div className="flex" style={{ paddingLeft: `${indent}px` }}>
              <span className="w-4 inline-block mr-1" />
              <span className="text-muted-foreground">{}</span>
              {!isLast && <span className="text-muted-foreground">,</span>}
            </div>
          </>
        )}
      </div>
    );
  }

  return null;
};

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
        const response = await fetch(getFileContentUrl(fileId));
        if (!response.ok) throw new Error(`Failed to fetch (${response.status})`);
        const text = await response.text();
        const parsed = JSON.parse(text);
        if (!cancelled) setData(parsed);
      } catch (err) {
        if (!cancelled) {
          if (err instanceof SyntaxError) setError("Invalid JSON: unable to parse");
          else setError(err instanceof Error ? err.message : "An error occurred");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    fetchJson();
    return () => { cancelled = true; };
  }, [fileId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full text-muted-foreground">
        <div className="flex items-center gap-2">
          <div className="w-5 h-5 border-2 border-muted border-t-primary rounded-full animate-spin" />
          Loading JSON...
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-full text-destructive">
        <div className="text-center">
          <p className="text-sm font-medium">Error</p>
          <p className="text-xs text-muted-foreground mt-1">{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full overflow-auto p-4 font-mono text-sm leading-6">
      <JsonNode value={data as JsonValue} depth={0} isLast={true} />
    </div>
  );
};

export default JsonViewer;
