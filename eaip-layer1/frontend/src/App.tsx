import { createBrowserRouter, RouterProvider, Navigate } from "react-router-dom";
import { RootLayout } from "./components/Layout/RootLayout";
import { ExplorerPage } from "./pages/ExplorerPage";
import { GraphPage } from "./pages/GraphPage";
import { PlaygroundPage } from "./pages/PlaygroundPage";
import { SearchPage } from "./pages/SearchPage";
import { IngestionDashboard } from "./pages/IngestionDashboard";

const router = createBrowserRouter([
  {
    path: "/",
    element: <RootLayout />,
    children: [
      { index: true, element: <ExplorerPage /> },
      { path: "graph", element: <GraphPage /> },
      { path: "playground", element: <PlaygroundPage /> },
      { path: "search", element: <SearchPage /> },
      { path: "ingestion", element: <IngestionDashboard /> },
      { path: "*", element: <Navigate to="/" replace /> },
    ],
  },
]);

export default function App() {
  return <RouterProvider router={router} />;
}
