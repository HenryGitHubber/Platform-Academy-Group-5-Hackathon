# Running the QuickSight Embedded Dashboard

## Every time you start (or credentials expire ~every hour)

1. **Open AWS CloudShell** — go to https://console.aws.amazon.com → click `>_` icon (top nav)

2. **Get fresh credentials** — run in CloudShell:
   ```
   aws configure export-credentials --format env
   ```

3. **Update `start-proxy.bat`** — open `front_end_5/proxy/start-proxy.bat` and replace:
   ```
   set AWS_ACCESS_KEY_ID=...
   set AWS_SECRET_ACCESS_KEY=...
   set AWS_SESSION_TOKEN=...
   ```
   with the 3 values from CloudShell output

4. **Start the proxy** — in a VS Code terminal:
   ```
   cmd //c "C:\...\front_end_5\proxy\start-proxy.bat"
   ```
   You should see: `✅ QuickSight embed proxy running on http://localhost:3001`

5. **Start Angular** — in a second VS Code terminal:
   ```
   npx --prefix "C:\...\front_end_5" ng serve
   ```
   Wait for: `Application bundle generation complete`

6. **Open the app** — http://localhost:4200

---

## Credentials expire?
Repeat steps 1–4. `ng serve` keeps running — no need to restart it.

## Visual IDs already configured
Sheet + visual IDs are hardcoded in `src/app/home/home.component.ts` → `quicksightPanels`.
To change which chart appears in a slot, run in CloudShell:
```
aws quicksight describe-dashboard-definition \
  --aws-account-id 339713122290 \
  --dashboard-id 1a71c9ed-29ed-4ac3-a540-9ea1e49182ef \
  --region us-east-1 \
  --query 'Definition.Sheets[*].{Sheet:SheetId,Visuals:Visuals[*].*.VisualId}' \
  --output json
```
Then update `sheetId` / `visualId` in the relevant panel.
