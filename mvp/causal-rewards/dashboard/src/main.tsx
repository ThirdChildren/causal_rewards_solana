/**
 * Entry point.
 *
 * The default source is the published audit bundle, not an RPC endpoint: the dashboard must
 * be useful and honest with no network beyond the static files it was served with. A devnet
 * RPC source is wired in behind the same interface when `VITE_RPC_ENDPOINT` is configured.
 */
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { BundleDataSource } from "./protocol/sources/bundleSource";
import "./styles/app.css";

const root = document.getElementById("root");
if (!root) throw new Error("no #root element");

createRoot(root).render(
  <StrictMode>
    <App source={new BundleDataSource({ root: "bundles" })} />
  </StrictMode>,
);
