# Example Slack Digest Output

## Before (Old Format)
```
🔍 **LobbyLens** — Daily Signals (2024-01-15) · 24h
Mini-stats: Bills 3 · FR 12 · Dockets 5 · High-priority 8

📈 **What Changed** (5):
• **Final Rule** — FAA Airworthiness Directives for Boeing 737 MAX... • regulatory action • <FR|View>
• **Proposed Rule** — EPA Clean Air Act Standards for Power Plants... • deadline in 30d • <FR|View>
• **Docket** — FDA Food Safety Modernization Act Comment Period... • 150 comments • <Docket|View>
• **Notice** — DOE Energy Efficiency Standards for Appliances... • government activity • <FR|View>
• **Hearing** — House Energy Committee Markup on Infrastructure Bill... • Energy Committee • <Congress|View>

🏭 **Industry Snapshot**:
• **Transportation**: 8 (3 rules, 5 notices)
• **Energy**: 6 (2 rules, 4 notices)
• **Health**: 4 (1 rules, 3 notices)

🧪 **Outlier**:
• **High Impact** — Major Climate Change Regulation Proposed by EPA... • <FR|View>

/lobbylens more · Updated 14:30 PT
```

## After (New Format)
```
🔍 *LobbyLens* — Daily Signals (2024-01-15) · 24h
Mini-stats: Bills 3 | FR 12 | Dockets 5 | High-priority 8

📈 *What Changed* (5):

Rules:
• Final Rule — FAA Airworthiness Directives for Boeing 737 MAX Aircraft Safety Updates • regulatory action • <FR|View>
• Proposed Rule — EPA Clean Air Act Standards for Power Plants Emissions • deadline in 30d • <FR|View>

Dockets:
• Docket — FDA Food Safety Modernization Act Comment Period Extended • 150 comments • <Docket|View>

Notices:
• Notice — DOE Energy Efficiency Standards for Appliances Updated • government activity • <FR|View>
• Hearing — House Energy Committee Markup on Infrastructure Bill • Energy Committee • <Congress|View>

🏭 *Industry Snapshot*:
• Transportation: 8 (3 rules, 5 notices)
• Energy: 6 (2 rules, 4 notices)
• Health: 4 (1 rules, 3 notices)

🧪 *High-Priority* (3):

Rules:
• Final Rule — FDA Emergency Use Authorization for New Drug • effective in 15d • <FR|View>
• Proposed Rule — DOT Autonomous Vehicle Safety Standards • deadline in 45d • <FR|View>

Notices:
• Notice — SEC Cybersecurity Disclosure Requirements • government activity • <FR|View>

/lobbylens more · Updated 14:30 PT
```

## Key Improvements

1. **Cleaner Headers**: `*LobbyLens*` instead of `**LobbyLens**`
2. **Better Separators**: `|` instead of `·` in mini-stats
3. **Grouped What Changed**: Organized by Rules, Dockets, Notices with clear headers
4. **All High-Priority Signals**: Shows all 8 high-priority items instead of just 1 outlier
5. **No Ellipses**: Clean truncation at word boundaries
6. **Selective Bold**: Only "**High Impact**" and meaningful keywords are bolded
7. **Consistent Formatting**: All section headers use the same `*text*` style
