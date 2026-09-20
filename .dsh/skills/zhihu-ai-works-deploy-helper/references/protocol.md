# CloudBase source-build protocol 1.2

## Blocking finding contract

A blocked deploy plan must contain at least one error finding. Every error finding must contain non-empty `Evidence`, `Reason`, and `Remediation`: evidence identifies the file, configuration, log, command result, or official source that supports the block; reason states the violated project/platform/protocol constraint; remediation gives concrete repair or escalation steps and the revalidation condition. A blocked status without this basis and self-heal guidance is invalid.

## Optional event-tracking bridge

Every plan contains `EventTrackingBridge`. HTTP backend plans confirmed to serve only APIs use `Status: not-applicable`. Static frontend, SSR, and reviewed Node-hosted HTML page plans use `injected` only when a deterministic source adapter atomically inserted the versioned inline script; otherwise they use `skipped` and emit `W_EVENT_TRACKING_BRIDGE_SKIPPED` without blocking delivery. The contract records protocol version, CSP-compatible script SHA-256, absolute endpoint, ticket environment variable and placeholder, parent-origin policy, adapter, target source, reason and evidence.

The endpoint is the built-in constant `https://tracking.aiworks.site/api/v1/event_tracking`. It is embedded as a public literal in the generated inline script and cannot be supplied or overridden through CLI arguments, project environment variables, or runtime configuration. Validation rejects an injected plan or source whose endpoint differs from this value.

When embedded, the bridge listens immediately for `message`, accepts only the first JSON object whose source is `window.parent` and whose origin is HTTPS on `zhihu.com` or a `.zhihu.com` subdomain, then removes the listener. When `window.self === window.top`, it instead reports one default PageShow after load with null member identifiers, `location.href`, `Date.now()`, `is_iframe_show: 0`, and `p_platform: desktopweb`; it does not register the message listener. Its JavaScript bytes are one fixed constant. The source template carries the single `__AIWORKS_EVENT_TRACKING_TICKET__` placeholder only in `data-aiworks-event-tracking-ticket`; the script reads it through `document.currentScript.dataset`. Before every frontend or page-rendering backend build—and before build-free hosting deploy—the generated `_tmp/materialize-event-tracking-ticket.cjs` atomically replaces that placeholder from `AIWORKS_EVENT_TRACKING_TICKET` and then invokes the original frontend build when one exists. At startup the helper emits exactly one diagnostic status, `[aiworks:event-tracking] AIWORKS_EVENT_TRACKING_TICKET=present|missing`; it never prints the ticket value. The frontend package receives deterministic `scripts.build:track`; package-free static delivery receives a generated root `package.json` marked with `aiworksEventTrackingBuild: 1`. Frontend `BuildCmd` is `npm run build:track` at root, `npm run build:track --workspace <name>` for workspace frontends, or `npm run build:track --prefix <directory>` for ordinary nested frontends. It must not directly invoke `node`, `sh`, `echo`, inline JavaScript or shell chaining. The helper resolves the project root from `__dirname`, so every npm entry has identical materialization and build behavior. A pre-existing different `build:track`, incompatible package marker, invalid package, or unsafe package target skips bridge injection with `W_EVENT_TRACKING_BRIDGE_SKIPPED` before source modification. Empty input leaves the inert placeholder unchanged but still runs the original build; non-empty input must match `[A-Za-z0-9_-]{1,256}`. Materialization never changes the script SHA-256. Every request forces `deploy_uuid: ticket`, uses `application/json`, and has a 1 MiB serialized-body limit. The bridge does not retry, persist or expose the event/ticket through a global. Skipped injection must preserve the source and cannot prevent descriptor or archive generation.

## Static output

Pure static projects contain `_tmp/deploy-plan.json` and `_tmp/frontend.deploy.json` as generated inputs, plus `_tmp/materialize-event-tracking-ticket.cjs` and the injected frontend package script exactly when the bridge is injected. Package-free static input additionally receives a generated root `package.json`. A root `cloudbaserc.json` is forbidden on this branch. The frontend descriptor keeps the existing Framework, NodeVersion, BuildCmd, InstallCmd, DeployCmd, BuildPath semantics and adds:

```json
{"SchemaVersion":"<DEPLOY_SCHEMA_VERSION>","Env":[]}
```

Both frontend and backend descriptor generators import the Skill-internal `DEPLOY_SCHEMA_VERSION` from `scripts/skill_config.py`. The validator compares emitted values with the same constant. The public `manifest.json` update interface does not contain this deployment-protocol setting; JSON Schema files validate only its semantic-version shape and are not a second value source.

Build-free static delivery uses `Framework: other` and an empty install command. Its build command is empty when no event bridge was injected; otherwise it contains only the deterministic ticket-materialization command before hosting deploy.

The build-only `AIWORKS_EVENT_TRACKING_TICKET` is exempt from the detector's unsupported-environment finding because HostingService supplies it during ticket materialization. It is deliberately not exported by the runtime bootstrap; runtime and build allowlists are separate entries in the shared Skill configuration.

## Backend output

```json
{
  "SchemaVersion": "<DEPLOY_SCHEMA_VERSION>",
  "Runtime": "node",
  "NodeVersion": "<detected-node-major>",
  "InstallDependencies": true,
  "Routes": [],
  "Env": [],
  "CustomSteps": [
    {"Name": "安装构建依赖", "Command": "npm ci"}
  ]
}
```

`CustomSteps` is a non-empty array of objects. Every element contains exactly one non-empty display `Name` and one non-empty shell `Command`; string elements are invalid. Both fields must be single-line strings without CR/LF. Multiple shell operations in one `Command` use inline ` && ` separators, never literal newlines. Steps execute, in order: full install, workspace/backend build, optional overlay switch, production install, runtime verification, CloudBase CLI install, login/deploy.

`NodeVersion` is not a framework or protocol allowlist. The detector normalizes a single project Node major from an explicit reviewed override, component `.nvmrc`/`.node-version`, or `package.json#engines.node`, and the generator copies that value unchanged into `backend.deploy.json`. `scf_bootstrap` does not encode a versioned Node binary path. If the project declares no unique major, the current compatibility fallback is `20` with `W_NODE_VERSION_FALLBACK`; the warning must be disclosed and the target runtime checked before execution.

Every backend component additionally contains deterministic `CloudFunctionRuntime` with `Runtime`, `InstallDependency` and `Source`. This does not change `NodeVersion`: it controls only root `cloudbaserc.json`. Auto-mapping rounds the detected major upward through fixed targets 16, 18, 20, 22 and 24, producing `Nodejs16.13`, `Nodejs18.15`, `Nodejs20.19`, `Nodejs22.21` or `Nodejs24.11`. Targets 16, 18 and 20 use `installDependency: true`; targets 22 and 24 use false. A detected major above 24 emits `E_CLOUDBASERC_RUNTIME_UNSUPPORTED`. Only after explicit user authorization may the Agent rerun with `--backend-cloud-function-node-version 24`; that reviewed override leaves the detected `NodeVersion` unchanged.

All backend and SSR outputs contain root `cloudbaserc.json` with fixed environment placeholders, `functionRoot: "."`, one HTTP function, and the runtime/installDependency pair from `CloudFunctionRuntime`. The validator reconstructs this file exactly; missing, extra or altered values are invalid.

Backend `OutputPath` and `RuntimeEntry` are always normalized project-root-relative paths. Component declarations such as start/main entries and `tsconfig.outDir` are resolved against the component directory exactly once. A workspace declaration such as `server/tsconfig.json` with `outDir: "../dist/api"` therefore becomes `OutputPath: "dist/api"`; descriptor generation must use it directly and must not prepend `server/` again. When a Node entry already exists as committed source and the build only emits runtime-read assets, `OutputPath` stays null with a `source-entry` output fact; the build command is still recorded and executed before deploy, and the entry is not required to live inside a build output.

Every backend component also contains deterministic `RuntimeResolution`, `RuntimeLaunch`, `BuildRecipe` and `BuildArtifacts` values. `RuntimeLaunch` is the resolver-owned authoritative startup choice: `node-entry` contains an `Entry` equal to `RuntimeEntry`, while `npm-script` contains the safe script name in `Script`; both record `Source`. Runtime generators and validators consume this field and must not reopen a manifest to replace the choice. `BuildRecipe` is the authoritative ordered list of npm build steps; each step records `Kind` (`package-build`, `runtime-prepare` or verified `orchestrator`), package, project-root-relative directory, declared script, executed command, source and produced artifact paths. `BuildArtifacts` is the authoritative generated-output set; every item records `Role`, project-root-relative `Path`, `Required: true`, `Source` and `Verification`. Roles are closed to `server-runtime`, `runtime-assets` and `runtime-metadata`. One `RuntimeEntry` may depend on multiple artifacts.

`RuntimeResolution` records the selected resolver, output/entry source classes, optional versioned framework contract, and structured facts for build command, output path and runtime entry. A framework contract also declares `LaunchKind`, which must equal a root framework SSR component's `RuntimeLaunch.Kind`. Each fact includes `Fact`, `Source`, `Value` and `Method`. Build, output and entry facts must equal their final compatibility projections. `BuildCommand` projects the selected component's own recipe step. `OutputPath` projects the primary server artifact containing `RuntimeEntry`, or stays null for a committed source entry. `WorkspaceDeps.BuildOrder` projects the recipe's workspace prefix. A non-blocked plan may not contain `pending-agent-configuration` or `unresolved-dynamic-config` sources.

`WorkspaceGraphs.BuildGraph` includes local dependencies, optionalDependencies and devDependencies used to order builds and detect cycles. `WorkspaceGraphs.RuntimeGraph` includes only dependencies and optionalDependencies used by the production closure. A cyclic static BuildGraph blocks delivery unless a separately authorized and recorded root orchestrator build replaces it.

Next standalone recipes include a deterministic runtime preparation after `next build`: copy `<distDir>/static` beneath the standalone directory at the distDir-relative location expected by the generated server, and copy committed `public` to `standalone/public` when present. The prepared paths are required `runtime-assets`; merely recording sibling build output is insufficient.

Configurable framework defaults are not accepted as final path evidence. Versioned fixed rules come from `node-framework-contracts.json` and must record the exact package-lock version and matching contract ID. If static evaluation cannot prove the output, the Agent may build under its own authorization, then supply project-root-relative output/entry overrides together with `BuildValidation`. Validation records successful npm install/build commands, cwd, exit status, npm lockfile, fresh artifacts and the final entry. A start probe is required only when the entry/start pairing cannot be proven statically; it uses the final entry, `0.0.0.0:9000`, a 30-second timeout and any valid HTTP response. Full logs and local outputs are not protocol inputs.

The delivery package manager is npm. When an isolated source has no npm lockfile or originated from another manager, the Agent first attempts npm install. Successful conversion retains `package-lock.json` and excludes pnpm/yarn locks and manager-only runtime files; only an actual npm failure blocks for a targeted source fix.

The backend deploy command contains the literal `${functionName}` token as its function-name argument. Descriptor generation must not derive a function name from the processed project directory or package manifest. The downstream consumer owns validation and replacement of this placeholder before execution.

Backend and SSR runtime source may consume only the environment names deterministically exported by the generated bootstrap: `PORT`, `HOST`, `HOSTNAME`, `NITRO_HOST` and `NITRO_PORT`. The detector and bootstrap generator consume one shared allowlist. Any other named or dynamic `process.env` access emits `E_USER_ENVIRONMENT_VARIABLE_UNSUPPORTED` and blocks descriptor and archive generation; the finding reports only the variable name when statically available and source evidence, never its value. The detector does not classify sensitivity. After the user is told that remediation stores all values as plaintext in project source and the ZIP, explicit authorization allows the Agent to replace every reported access with project-local literals in the isolated delivery source and rerun detection; without authorization the plan remains blocked.

The runtime-only statement above describes bootstrap exports. For detector purposes, `AIWORKS_EVENT_TRACKING_TICKET` is an additional build-time exception supplied by HostingService and is not a runtime environment contract.

## Generated Node inputs

All Node/SSR projects contain root `cloudbaserc.json`, a deterministic projection of `CloudFunctionRuntime`.

All Node/SSR projects contain root `scf_bootstrap`, whose command is a deterministic projection of `RuntimeLaunch`. Current Next/vinext standalone, Nuxt/Nitro node-server and SvelteKit adapter-node contracts select direct `exec node <RuntimeEntry>` so a generic root framework start script cannot bypass the resolved delivery artifact. Root ordinary Node, Nest and hand-written SSR monoliths select `exec npm run start` when their runtime manifest has a non-empty start script, preserving script-specific startup behavior; otherwise they select direct entry. Overlay selects `exec npm run start` against its generated manifest. A versioned absolute Node path is forbidden. Overlay projects additionally contain `_tmp/backend.runtime.package.json` and `_tmp/prepare-backend-package.js`; the generated overlay manifest always supplies the start script. Root projects must not contain overlay files.

The preparation script performs no discovery. It validates the precomputed manifest and entry, copies the manifest to a temporary file in the project root, then atomically renames it to `package.json`.

Local workspace dependencies are rewritten to `file:./<directory>`. If a local runtime package itself contains a transitive `workspace:` declaration, preparation blocks: a root-only overlay cannot safely rewrite that child manifest without violating the source-preservation contract.

## Archive

Backend archives require a regular root `cloudbaserc.json`; static archives reject that file.

The archiver accepts only `Status: ready` or `Status: review-required` plans with no error finding. It rejects inconsistent plans that retain `E_IFRAME_EMBEDDING_FORBIDDEN` or any other error finding even when their status is not blocked.

Archive generation requires a non-blocked deploy plan; the archiver rejects `Status: blocked` and removes any stale same-name output instead of preserving or delivering it. Archive the source project with a single project-directory prefix. Replace every whitespace character in the source directory name with `_` for the ZIP filename, ZIP root prefix and frontend `BuildPath`; the isolated source directory itself is not renamed. Recursively exclude VCS metadata, dependencies, common generated directories (`dist`, `build`, `out`, `.next`, `.nuxt`, `.output`, `.svelte-kit`, `.vite`, `.turbo`, coverage/cache), exact `BuildArtifacts`, pnpm/yarn locks and manager-only runtime files, secrets, links, devices, current and legacy self-generated archive names, and operating-system metadata. A committed build-free `RuntimeEntry` is protected from the common-directory rule. macOS exclusions include `__MACOSX`, `.AppleDouble`, `.DocumentRevisions-V100`, `.fseventsd`, `.Spotlight-V100`, `.TemporaryItems`, `.Trash`, `.Trashes`, `.DS_Store`, `.localized`, `.VolumeIcon.icns`, `Icon\r`, and `._*` AppleDouble files. Reopen the ZIP and reject any forbidden member after writing. The archive itself is mode `0666`.


### Node-hosted HTML event tracking

A standalone `node-http` component may carry `HtmlPages`, an Agent-reviewed array of `{Path, Reason, Evidence: [{File, Line, Text}]}`. Deployment classification and runtime launch do not change. These records attest the reachable backend response-to-HTML relationship; the detector checks the referenced regular project files and exact source lines, not arbitrary JavaScript semantics. The validator checks the evidence again to reject stale records.

For these pages the injected bridge has `Adapter: backend-html`, sorted unique `TargetFiles`, and `TargetFile` equal to the first element for single-target compatibility. Every target must match the fixed bridge bytes and ticket contract. The materializer checks all placeholders before writing any page and atomically replaces each file; it logs ticket presence once. Backend CustomSteps run it before the build or source-entry check, using the existing backend-only path. No frontend descriptor or `build:track` package script is created for this case. The generated helper and all source HTML pages must be included in the project ZIP. This optional plan metadata does not change either deployment descriptor's schema.


### Repeated preparation and generated startup files

`scf_bootstrap` and deployment descriptors are generator-owned delivery outputs, not source requirements for the user to resolve. Once ownership of existing outputs is established, re-detect the real application source and regenerate them from the current plan. Existing, stale, or different generated startup commands do not block preparation or require renewed overwrite approval. Validate the regenerated outputs and archive normally. Unknown custom files still require ownership review. Generic documentation examples, absolute-path wording alone, and lack of a live cloud startup test do not establish a platform incompatibility; only concrete evidence applicable to the target runtime activates that gate.
