import os
import re
import json

files = [
    "src/index.css",
    "tailwind.config.js",
    "src/main.tsx",
    "src/App.tsx",
    "src/components/Sidebar.tsx",
    "src/components/TopBar.tsx",
    "src/components/MainCanvas.tsx",
    "src/components/DisclaimerModal.tsx",
    "src/components/OmniSearchBar.tsx",
    "src/pages/CommandCenterPage.tsx",
    "src/pages/PlayerProfilePage.tsx",
    "src/pages/MatchupEnginePage.tsx",
    "src/pages/MatchupLabPage.tsx",
    "src/pages/TeamCentralPage.tsx",
    "src/pages/SettingsPage.tsx",
    "src/pages/PulsePage.tsx",
    "src/pages/VanguardControlRoom.tsx",
    "src/pages/BoxScoresPage.tsx",
    "src/pages/InjuryAdmin.tsx",
    "src/pages/AboutPage.tsx",
    "src/components/PlayByPlay/PlayByPlay.css",
    "src/components/aegis/MatchupWarRoom.css",
    "src/components/common/ErrorBoundaryWithFallback.css",
    "src/components/common/FreshnessHalo.css",
    "src/components/common/NextDayDriftToast.css",
    "src/components/common/WhyTooltip.css",
    "src/components/matchup/FrictionHeatMap.css",
    "src/components/matchup/ProgressiveLoadingSkeleton.css",
    "src/components/matchup/UsageVacuumToggle.css",
    "src/pages/MatchupLabPage.css",
    "src/components/common/MetricCard.tsx",
    "src/components/common/StatusLed.tsx",
    "src/components/common/Sparkline.tsx",
    "src/components/common/ConfidenceRing.tsx",
    "src/components/common/Modal.tsx",
    "src/components/common/ToastContainer.tsx",
    "src/components/common/WhyTooltip.tsx",
    "src/components/common/CascadingSelector.tsx",
    "src/components/common/ConnectionStatus.tsx",
    "src/components/common/DataProvenanceBadge.tsx",
    "src/components/common/DefenderImpactTooltip.tsx",
    "src/components/common/FatigueBreakdownChip.tsx",
    "src/components/common/ResponsiveContainer.tsx",
    "src/components/common/ResponsiveGrid.tsx",
    "src/components/common/SectionErrorBoundary.tsx",
    "src/components/common/ConfirmDialog.tsx",
    "src/components/common/ErrorBoundaryWithFallback.tsx",
    "src/components/profile/HeroSection.tsx",
    "src/components/profile/NarrativeBlock.tsx",
    "src/components/profile/ProbabilityGauge.tsx",
    "src/components/profile/EnrichedPlayerCard.tsx",
    "src/components/matchup/MatchupRadar.tsx",
    "src/components/matchup/FrictionHeatMap.tsx",
    "src/components/matchup/InsightBanner.tsx",
    "src/components/matchup/UsageVacuumToggle.tsx",
    "src/components/matchup/ProgressiveLoadingSkeleton.tsx",
    "src/components/aegis/MatchupWarRoom.tsx",
    "src/components/aegis/ProjectionMatrix.tsx",
    "src/components/aegis/PlayTypeEfficiency.tsx",
    "src/components/aegis/VertexMatchupCard.tsx",
    "src/components/player/GameLogsViewer.tsx",
    "src/components/player/H2HHistoryPanel.tsx",
    "src/components/player/PlayerShotChart.tsx",
    "src/components/vanguard/VanguardHealthWidget.tsx",
    "src/components/vanguard/VanguardControlRoom.tsx",
    "src/components/vanguard/VanguardArchivesViewer.tsx",
    "src/components/vanguard/VanguardLearningExport.tsx",
    "src/components/vanguard/VaccinePanel.tsx",
    "src/components/PlayByPlay/PlayByPlayFeed.tsx",
    "src/components/PlayByPlay/PlayItem.tsx",
    "src/components/PlayByPlay/GameScoreHeader.tsx",
    "src/components/PlayByPlay/LiveGameSelector.tsx",
    "src/components/PlayByPlay/InteractiveShotChart.tsx",
    "src/components/PlayByPlay/ConnectionStatus.tsx",
    "src/components/dashboard/BoxScoreViewer.tsx",
    "src/components/settings/HealthDepsPanel.tsx",
    "src/components/ui/alert.tsx",
    "src/components/ui/button.tsx",
    "src/components/ui/card.tsx",
    "src/components/ui/input.tsx",
    "src/components/ui/label.tsx",
    "src/components/ui/select.tsx",
    "src/components/ui/index.tsx"
]

results = {
    'hardcoded_colors': [],
    'style_overrides': [],
    'important_css': [],
    'todos_hacks': [],
    'console_logs': [],
    'spacing_classes': {}
}

color_re = re.compile(r'(#[0-9a-fA-F]{3,8}|rgba?\([\d\s,.]+\))')
style_re = re.compile(r'style=\{\{')
important_re = re.compile(r'!important')
todo_re = re.compile(r'(?i)(TODO|FIXME|hack|temp|placeholder)')
console_re = re.compile(r'console\.(log|error|warn)')
spacing_re = re.compile(r'\b([pm][xytrbl]?-\d+|gap-\d+|space-[xy]-\d+)\b')

for fpath in files:
    try:
        with open(fpath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            for i, line in enumerate(lines):
                line_idx = i + 1
                
                # Colors
                if fpath != 'tailwind.config.js': # skip config
                    colors = color_re.findall(line)
                    for c in colors:
                        # try to avoid false positives in valid comments or SVGs
                        if 'xmlns' not in line:
                            results['hardcoded_colors'].append({'file': fpath, 'line': line_idx, 'match': c})
                            
                # Style overrides
                if style_re.search(line):
                    results['style_overrides'].append({'file': fpath, 'line': line_idx, 'match': line.strip()})
                    
                # Important CSS
                if important_re.search(line):
                    results['important_css'].append({'file': fpath, 'line': line_idx, 'match': line.strip()})
                    
                # TODOs
                todos = todo_re.findall(line)
                if todos:
                    results['todos_hacks'].append({'file': fpath, 'line': line_idx, 'match': line.strip()})
                    
                # Console logs
                if console_re.search(line):
                    results['console_logs'].append({'file': fpath, 'line': line_idx, 'match': line.strip()})
                    
                # Spacing
                if fpath.endswith('.tsx') or fpath.endswith('.ts') or fpath.endswith('.jsx'):
                    matches = spacing_re.findall(line)
                    for m in matches:
                        results['spacing_classes'][m] = results['spacing_classes'].get(m, 0) + 1

    except FileNotFoundError:
        print(f"Skipping {fpath} - not found.")
    except Exception as e:
        print(f"Error reading {fpath}: {e}")

with open('audit_results.json', 'w', encoding='utf-8') as f:
    json.dump(results, f, indent=2)

print("Done generating audit_results.json")
